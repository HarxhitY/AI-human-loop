# app.py
import os
import uuid
import json
import threading
import time
from datetime import datetime, timezone
from flask import Flask, request, render_template, redirect, url_for, flash
import boto3
from boto3.dynamodb.conditions import Attr
from dotenv import load_dotenv
import requests

load_dotenv()

DYNAMO_ENDPOINT = os.getenv('DYNAMO_ENDPOINT', 'http://localhost:8000')
REGION = os.getenv('REGION', 'us-west-2')
SUPERVISOR_WEBHOOK = os.getenv('SUPERVISOR_WEBHOOK', 'http://localhost:5000/simulate_notification')
SUPERVISOR_TIMEOUT_SECONDS = int(os.getenv('SUPERVISOR_TIMEOUT_SECONDS', '90'))

app = Flask(__name__)
app.secret_key = 'dev-secret'  # for flash messages in UI

dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMO_ENDPOINT, region_name=REGION)
help_table = dynamodb.Table('HelpRequests')
kb_table = dynamodb.Table('KnowledgeBase')


# ---------------------------
# Simple pages
# ---------------------------
@app.route('/')
def index():
    return "HITL LiveKit Salon Agent - Supervisor UI available at /supervisor"


@app.route('/supervisor')
def supervisor_index():
    resp = help_table.scan()
    requests_list = sorted(resp.get('Items', []), key=lambda r: r.get('created_at', ''), reverse=True)
    return render_template('supervisor_index.html', requests=requests_list)


@app.route('/learned')
def learned():
    resp = kb_table.scan()
    items = resp.get('Items', [])
    return render_template('learned.html', kb=items)


@app.route('/request/<request_id>', methods=['GET'])
def view_request(request_id):
    resp = help_table.get_item(Key={'request_id': request_id})
    item = resp.get('Item')
    if not item:
        flash('Request not found', 'error')
        return redirect(url_for('supervisor_index'))
    return render_template('request_detail.html', req=item)


@app.route('/request/<request_id>/resolve', methods=['POST'])
def resolve_request(request_id):
    answer = request.form.get('answer', '').strip()
    resolved = request.form.get('resolved', 'true') == 'true'

    now = datetime.now(timezone.utc).isoformat()
    status = 'Resolved' if resolved else 'Unresolved'

    help_table.update_item(
        Key={'request_id': request_id},
        UpdateExpression='SET #s = :s, resolved_at = :r, supervisor_answer = :a',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': status, ':r': now, ':a': answer}
    )

    # Persist to KnowledgeBase if resolved
    if resolved and answer:
        resp = help_table.get_item(Key={'request_id': request_id})
        req_item = resp.get('Item', {})
        kb_table.put_item(Item={
            'kb_key': f"request#{request_id}",
            'question': req_item.get('question'),
            'answer': answer,
            'created_at': now,
            'source_request': request_id
        })

    # Notify caller
    resp = help_table.get_item(Key={'request_id': request_id})
    caller = resp.get('Item', {}).get('caller', {})
    simulate_text_back(caller, answer or "No answer provided.", request_id)

    flash('Request updated and caller notified.', 'success')
    return redirect(url_for('supervisor_index'))


# ---------------------------
# Simulated notification endpoint
# ---------------------------
@app.route('/simulate_notification', methods=['POST'])
def simulate_notification():
    payload = request.json or {}
    print("=== Supervisor notification ===")
    print(json.dumps(payload, indent=2))
    return {'status': 'ok'}


def simulate_text_back(caller_meta, answer_text, request_id):
    payload = {
        'to': caller_meta,
        'message': f"Update to your question (request {request_id}): {answer_text}",
        'request_id': request_id,
        'ts': datetime.now(timezone.utc).isoformat()
    }
    try:
        requests.post(SUPERVISOR_WEBHOOK, json=payload, timeout=2)
    except Exception as e:
        print("Failed to POST to webhook; logging instead:", e)
        print(json.dumps(payload, indent=2))


# ---------------------------
# Webhook endpoint for LiveKit or simulated inbound call
# ---------------------------
@app.route('/livekit_webhook', methods=['POST'])
def livekit_webhook():
    data = request.json or {}
    if data.get('type') == 'inbound_call':
        caller = data.get('caller', {})
        question = data.get('question', '').strip()

        # Check knowledge base for similar question
        kb_resp = kb_table.scan()
        for k in kb_resp.get('Items', []):
            stored_q = k.get('question', '')
            if question.lower() in stored_q.lower() or stored_q.lower() in question.lower():
                answer = k['answer']
                print(f"[Agent] Known answer found for '{question}': {answer}")
                return {'status': 'answered', 'answer': answer}

        # Unknown -> escalate
        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        help_table.put_item(Item={
            'request_id': request_id,
            'status': 'Pending',
            'created_at': now,
            'caller': caller,
            'question': question,
            'supervisor_answer': None
        })

        notif_payload = {
            'type': 'help_request',
            'request_id': request_id,
            'question': question,
            'caller': caller,
            'created_at': now
        }
        try:
            requests.post(SUPERVISOR_WEBHOOK, json=notif_payload, timeout=2)
        except Exception as e:
            print("Failed to notify supervisor webhook:", e)

        print("[Agent -> Caller] Let me check with my supervisor and get back to you.")
        return {'status': 'escalated', 'request_id': request_id, 'message': "Let me check with my supervisor and get back to you."}

    return {'status': 'ignored', 'detail': 'unsupported event'}


# ---------------------------
# Background timeout worker
# ---------------------------
def timeout_worker():
    while True:
        try:
            now_ts = time.time()
            resp = help_table.scan(FilterExpression=Attr('status').eq('Pending'))
            for it in resp.get('Items', []):
                created_str = it.get('created_at')
                try:
                    created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    created_ts = created_dt.timestamp()
                except Exception:
                    continue

                if now_ts - created_ts > SUPERVISOR_TIMEOUT_SECONDS:
                    help_table.update_item(
                        Key={'request_id': it['request_id']},
                        UpdateExpression='SET #s = :s, resolved_at = :r',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={':s': 'Unresolved', ':r': datetime.now(timezone.utc).isoformat()}
                    )
                    simulate_text_back(
                        it.get('caller', {}),
                        "Sorry, we couldn't get an answer in time. We'll follow up soon.",
                        it['request_id']
                    )
            time.sleep(5)
        except Exception as e:
            print("Timeout worker error:", e)
            time.sleep(5)


if __name__ == "__main__":
    t = threading.Thread(target=timeout_worker, daemon=True)
    t.start()
    app.run(debug=True, port=5000)
