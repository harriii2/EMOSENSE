import os
import secrets
import smtplib
import mysql.connector
from datetime import datetime, timedelta
from email.message import EmailMessage
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'emosense_db')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', EMAIL_USER or 'noreply@localhost')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
PASSWORD_RESET_EXPIRY_MINUTES = int(os.getenv('PASSWORD_RESET_EXPIRY_MINUTES', '30'))


def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False
    )


def init_auth_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(100),
            location VARCHAR(255),
            trusted_email VARCHAR(255),
            password VARCHAR(255) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        '''
    )
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            token VARCHAR(255) NOT NULL UNIQUE,
            expires_at DATETIME NOT NULL,
            used TINYINT(1) DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        '''
    )
    conn.commit()
    cursor.close()
    conn.close()


def send_reset_email(to_email, token):
    if not EMAIL_HOST or not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError('Email settings are not fully configured. Set EMAIL_HOST, EMAIL_USER and EMAIL_PASSWORD.')

    reset_url = request.url_root.rstrip('/') + f'/reset-password?token={token}'
    msg = EmailMessage()
    msg['Subject'] = 'EmoSense Password Reset'
    msg['From'] = EMAIL_FROM
    msg['To'] = to_email
    msg.set_content(f"""
Hi,

We received a request to reset your EmoSense password. Click the link below to choose a new password:

{reset_url}

This link expires in {PASSWORD_RESET_EXPIRY_MINUTES} minutes.

If you did not request this, you can ignore this email.

Thanks,
EmoSense Team
""")

    if EMAIL_USE_SSL:
        server = smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=10)
    else:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=10)
        server.ehlo()
        if EMAIL_USE_TLS:
            server.starttls()
            server.ehlo()
    try:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            'SMTP authentication failed. Check EMAIL_USER and EMAIL_PASSWORD and use a Gmail app password if required.'
        ) from exc
    finally:
        server.quit()


def register_auth_routes(app):
    @app.route('/auth/login', methods=['POST'])
    def login():
        data = request.get_json() or request.form
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required.'})

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            return jsonify({'success': True, 'name': user['full_name'], 'email': user['email']})
        return jsonify({'success': False, 'message': 'Invalid credentials'})

    @app.route('/auth/register', methods=['POST'])
    def register():
        data = request.get_json() or request.form
        full_name = (data.get('full_name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        phone = (data.get('phone') or '').strip()
        location = (data.get('location') or '').strip()
        trusted_email = (data.get('trusted_email') or '').strip().lower()
        password = data.get('password') or ''
        confirm_password = data.get('confirm_password') or ''

        if not full_name or not email or not phone or not location or not trusted_email or not password or not confirm_password:
            return jsonify({'success': False, 'message': 'All fields are required.'})

        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match.'})

        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (full_name, email, phone, location, trusted_email, password) VALUES (%s, %s, %s, %s, %s, %s)',
                (full_name, email, phone, location, trusted_email, hashed_password)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True})
        except mysql.connector.IntegrityError as exc:
            if exc.errno == 1062:
                return jsonify({'success': False, 'message': 'A user with that email already exists.'})
            return jsonify({'success': False, 'message': str(exc)})
        except Exception as exc:
            return jsonify({'success': False, 'message': str(exc)})

    @app.route('/auth/forgot', methods=['POST'])
    def forgot():
        data = request.get_json() or request.form
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': 'Please enter your email address.'})

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRY_MINUTES)
            cursor.execute(
                'INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)',
                (user['id'], token, expires_at.strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            try:
                send_reset_email(email, token)
            except Exception as exc:
                print('Password reset email failed:', exc)
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'message': 'Could not send reset email. Check SMTP credentials and mail settings.'
                })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'If this email is registered, a password reset link has been sent.'
        })

    @app.route('/auth/reset-password', methods=['POST'])
    def reset_password():
        data = request.get_json() or request.form
        token = (data.get('token') or '').strip()
        password = data.get('password') or ''
        confirm_password = data.get('confirm_password') or ''

        if not token or not password or not confirm_password:
            return jsonify({'success': False, 'message': 'Token and new password are required.'})

        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match.'})

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT id, user_id FROM password_resets WHERE token = %s AND used = 0 AND expires_at >= UTC_TIMESTAMP()',
            (token,)
        )
        reset_row = cursor.fetchone()

        if not reset_row:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'This reset link is invalid or has expired.'})

        hashed_password = generate_password_hash(password)
        cursor.execute('UPDATE users SET password = %s WHERE id = %s', (hashed_password, reset_row['user_id']))
        cursor.execute('UPDATE password_resets SET used = 1 WHERE id = %s', (reset_row['id'],))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Your password has been reset successfully.'})
