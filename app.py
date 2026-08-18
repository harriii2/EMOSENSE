import os, base64, numpy as np, cv2
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import requests as req

load_dotenv()  # reads .env
from auth.auth_routes import init_auth_db, register_auth_routes
from auth.auth_routes import get_db

app = Flask(__name__)
register_auth_routes(app)
init_auth_db()

# ── Load your CNN model once at startup ──
from tensorflow.keras.models import load_model
model = load_model('model.h5')
EMOTIONS = ['Angry','Disgust','Fear','Happy','Sad','Surprise','Neutral']

# ── Serve the frontend ──
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/reset-password')
def reset_password_page():
    return render_template('index.html', page='login')

# ── Emotion prediction endpoint ──
@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    img_data = data['image'].split(',')[1]           # strip "data:image/jpeg;base64,"
    img_bytes = base64.b64decode(img_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return jsonify({'emotion': 'No face detected'})

    x, y, w, h = faces[0]
    roi = gray[y:y+h, x:x+w]
    roi = cv2.resize(roi, (48, 48))
    roi = roi.astype('float32') / 255.0
    roi = np.expand_dims(roi, axis=[0, -1])          # shape: (1, 48, 48, 1)

    preds = model.predict(roi)[0]
    emotion = EMOTIONS[np.argmax(preds)]
    # confidence value removed from API response
    return jsonify({'emotion': emotion})

# ── Groq AI chat proxy endpoint ──
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    emotion = data.get('emotion', 'neutral')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}"
    }

    payload = {
        'model': 'openai/gpt-oss-120b',
        'messages': [
            {
                'role': 'system',
                'content': f"""You are EmoSense AI, a compassionate emotional wellness assistant built into a facial emotion detection app.
The user's latest detected emotion from the CNN model is: "{emotion}".
Respond with empathy and warmth, keeping responses to 2-3 sentences.
Naturally acknowledge their emotional state without being robotic about it.
You can suggest features like diary writing, music recommendations, or breathing exercises when relevant."""
            },
            {
                'role': 'user',
                'content': message
            }
        ],
        'temperature': 0.8,
        'max_tokens': 200
    }

    try:
        response = req.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=payload
        )
        result = response.json()
        print('Groq status:', response.status_code)
        print('Groq response:', result) 
        if 'choices' not in result:
            error_msg = result.get('error', {}).get('message', 'Unknown Groq error')
            return jsonify({'reply': f"Sorry, I couldn't respond right now."}), 500
        reply = result['choices'][0]['message']['content']
        return jsonify({'reply': reply})
    except Exception as e:
        print('Groq error:', e)
        return jsonify({'reply': 'Sorry, I could not respond right now. Please try again.'}), 500


@app.route('/api/emotion_history', methods=['POST', 'GET'])
def api_emotion_history():
    if request.method == 'POST':
        data = request.get_json() or request.form
        email = (data.get('email') or '').strip().lower()
        if not email:
            return jsonify({'success': False, 'message': 'Email required'}), 400
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close(); conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        payload = {
            'user_id': user['id'],
            'emotion': data.get('emotion'),
            'date': data.get('date'),
            'time': data.get('time')
        }
        cursor.execute('''INSERT INTO emotion_history (user_id, emotion, date, time)
                          VALUES (%s,%s,%s,%s)''',
                       (payload['user_id'], payload['emotion'], payload['date'], payload['time']))
        conn.commit()
        # After insert, check recent sad count and send alert if threshold reached
        try:
            cursor.execute('SELECT emotion FROM emotion_history WHERE user_id = %s ORDER BY id DESC LIMIT 10', (payload['user_id'],))
            recent = cursor.fetchall()
            sad_count = sum(1 for r in recent if r.get('emotion') and r.get('emotion').lower() == 'sad')
            if sad_count >= 3:
                cursor.execute('SELECT trusted_email FROM users WHERE id = %s', (payload['user_id'],))
                u = cursor.fetchone()
                trusted = u.get('trusted_email') if u else None
                if trusted:
                    try:
                        from auth.auth_routes import send_alert_email
                        subject = 'EmoSense Alert: Repeated Sad Detections'
                        body = f"EmoSense detected 'Sad' emotion {sad_count} times for user {email}. Please check in on them."
                        send_alert_email(trusted, subject, body)
                    except Exception as exc:
                        print('Alert email failed:', exc)
        except Exception:
            pass
        finally:
            cursor.close(); conn.close()
        return jsonify({'success': True})

    # GET
    email = request.args.get('email','').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'Email required'}), 400
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 404
    cursor.execute('SELECT emotion, date, time FROM emotion_history WHERE user_id = %s ORDER BY id DESC LIMIT 200', (user['id'],))
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify({'success': True, 'history': rows})


@app.route('/api/diary', methods=['POST','GET','PUT','DELETE'])
def api_diary():
    if request.method == 'POST':
        data = request.get_json() or request.form
        email = (data.get('email') or '').strip().lower()
        content = data.get('content') or ''
        if not email or not content:
            return jsonify({'success': False, 'message': 'Email and content required'}), 400
        conn = get_db(); cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close(); conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        created_at = data.get('created_at')
        if created_at:
            cursor.execute('INSERT INTO diary (user_id, content, created_at) VALUES (%s,%s,%s)',
                           (user['id'], content, created_at))
        else:
            cursor.execute('INSERT INTO diary (user_id, content) VALUES (%s,%s)', (user['id'], content))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close(); conn.close()
        return jsonify({'success': True, 'id': new_id})

    if request.method == 'GET':
        email = request.args.get('email','').strip().lower()
        if not email:
            return jsonify({'success': False, 'message': 'Email required'}), 400
        conn = get_db(); cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close(); conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        cursor.execute('SELECT id, content, created_at, updated_at FROM diary WHERE user_id = %s ORDER BY id DESC LIMIT 200', (user['id'],))
        rows = cursor.fetchall()
        for row in rows:
            if isinstance(row.get('created_at'), datetime):
                row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(row.get('updated_at'), datetime):
                row['updated_at'] = row['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
        cursor.close(); conn.close()
        return jsonify({'success': True, 'entries': rows})

    if request.method == 'PUT':
        data = request.get_json() or request.form
        entry_id = data.get('id')
        content = data.get('content') or ''
        if not entry_id or not content:
            return jsonify({'success': False, 'message': 'id and content required'}), 400
        conn = get_db(); cursor = conn.cursor()
        cursor.execute('UPDATE diary SET content = %s WHERE id = %s', (content, entry_id))
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'success': True})

    if request.method == 'DELETE':
        data = request.get_json() or request.form
        entry_id = data.get('id')
        if not entry_id:
            return jsonify({'success': False, 'message': 'id required'}), 400
        conn = get_db(); cursor = conn.cursor()
        cursor.execute('DELETE FROM diary WHERE id = %s', (entry_id,))
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, ssl_context='adhoc')