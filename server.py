import os
import re
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import boto3
from botocore.client import Config
from werkzeug.utils import secure_filename
import requests

load_dotenv()

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.nevaobjects.id")
S3_BUCKET = os.getenv("S3_BUCKET", "rizyyn")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", f"https://{S3_BUCKET}.s3.nevaobjects.id")
S3_PREFIX = os.getenv("S3_PREFIX", "audio/")
S3_PHOTO_PREFIX = os.getenv("S3_PHOTO_PREFIX", "photos/")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise SystemExit("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in environment")

app = Flask(__name__, static_folder='.', static_url_path='')

def make_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}),
    )


def public_url(key):
    key = key.lstrip('/')
    return f"{S3_PUBLIC_URL}/{key}"


def get_mime_type(extension):
    mime_map = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif',
        'svg': 'image/svg+xml',
        'heic': 'image/heic',
        'raw': 'image/x-raw',
        'arw': 'image/x-sony-arw',
        'mp4': 'video/mp4',
        'mkv': 'video/x-matroska',
        'mov': 'video/quicktime',
        'avi': 'video/x-msvideo',
        'webm': 'video/webm',
    }
    return mime_map.get(extension, 'application/octet-stream')


def slugify_album(name):
    if not name:
        return ''
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100]


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    return response


@app.route('/')
def index():
    return app.send_static_file('pesan-suara.html')


@app.route('/tracks', methods=['GET', 'DELETE'])
def tracks():
    client = make_s3_client()
    if request.method == 'DELETE':
        key = request.args.get('key', '').strip()
        if not key:
            return jsonify({'error': 'key parameter required'}), 400
        try:
            client.delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception as exc:
            return jsonify({'error': 'delete failed', 'details': str(exc)}), 500
        return jsonify({'deleted': key})

    paginator = client.get_paginator('list_objects_v2')
    objects = []

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('/'):
                continue
            if not key.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.webm')):
                continue
            objects.append({
                'title': os.path.basename(key),
                'key': key,
                'url': public_url(key),
                'size': obj['Size'],
                'lastModified': obj['LastModified'].isoformat(),
            })

    objects.sort(key=lambda item: item['title'].lower())
    return jsonify(objects)


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'file field is required'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'filename required'}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'invalid filename'}), 400

    extension = filename.rsplit('.', 1)[-1].lower()
    if extension not in {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'webm'}:
        return jsonify({'error': 'unsupported audio format'}), 400

    destination_key = f"{S3_PREFIX}{filename}"
    client = make_s3_client()
    content_type = file.mimetype or 'audio/mpeg'
    file_bytes = file.read()

    try:
        presigned_url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': destination_key,
                'ACL': 'public-read',
                'ContentType': content_type,
            },
            ExpiresIn=60,
        )

        response = requests.put(
            presigned_url,
            data=file_bytes,
            headers={
                'Content-Type': content_type,
                'x-amz-acl': 'public-read',
            },
            timeout=60,
        )

        if response.status_code not in (200, 201):
            return jsonify({'error': 'upload failed', 'details': response.text}), 500
    except Exception as exc:
        return jsonify({'error': 'upload failed', 'details': str(exc)}), 500

    return jsonify({'url': public_url(destination_key), 'title': filename, 'key': destination_key})


@app.route('/photo-albums')
def photo_albums():
    client = make_s3_client()
    paginator = client.get_paginator('list_objects_v2')
    folders = []

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PHOTO_PREFIX, Delimiter='/'):
        for prefix in page.get('CommonPrefixes', []):
            folder = prefix['Prefix']
            if folder.startswith(S3_PHOTO_PREFIX):
                slug = folder[len(S3_PHOTO_PREFIX):].rstrip('/')
                if slug:
                    folders.append(slug)

    folders.sort()
    return jsonify(folders)


@app.route('/photos', methods=['GET', 'DELETE'])
def photos():
    client = make_s3_client()
    if request.method == 'DELETE':
        key = request.args.get('key', '').strip()
        if not key:
            return jsonify({'error': 'key parameter required'}), 400
        if not key.startswith(S3_PHOTO_PREFIX):
            return jsonify({'error': 'invalid photo key'}), 400
        try:
            client.delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception as exc:
            return jsonify({'error': 'delete failed', 'details': str(exc)}), 500
        return jsonify({'deleted': key})

    album = slugify_album(request.args.get('album', ''))
    if not album:
        return jsonify({'error': 'album parameter invalid or missing'}), 400

    prefix = f"{S3_PHOTO_PREFIX}{album}/"
    paginator = client.get_paginator('list_objects_v2')
    objects = []

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('/'):
                continue
            objects.append({
                'key': key,
                'url': public_url(key),
                'filename': os.path.basename(key),
                'lastModified': obj['LastModified'].isoformat(),
            })

    objects.sort(key=lambda item: item['filename'].lower())
    return jsonify(objects)


@app.route('/photos/upload', methods=['POST'])
def photo_upload():
    album = slugify_album(request.form.get('album', ''))
    if not album:
        return jsonify({'error': 'album parameter invalid or missing'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'file field is required'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'filename required'}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'invalid filename'}), 400

    extension = filename.rsplit('.', 1)[-1].lower()
    if extension not in {'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg', 'heic', 'raw', 'arw', 'mp4', 'mkv', 'mov', 'avi', 'webm'}:
        return jsonify({'error': 'unsupported media format'}), 400

    destination_key = f"{S3_PHOTO_PREFIX}{album}/{filename}"
    client = make_s3_client()
    content_type = file.mimetype or get_mime_type(extension)
    file_bytes = file.read()

    try:
        presigned_url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': destination_key,
                'ACL': 'public-read',
                'ContentType': content_type,
            },
            ExpiresIn=60,
        )

        response = requests.put(
            presigned_url,
            data=file_bytes,
            headers={
                'Content-Type': content_type,
                'x-amz-acl': 'public-read',
            },
            timeout=60,
        )

        if response.status_code not in (200, 201):
            return jsonify({'error': 'upload failed', 'details': response.text}), 500
    except Exception as exc:
        return jsonify({'error': 'upload failed', 'details': str(exc)}), 500

    return jsonify({'url': public_url(destination_key), 'filename': filename, 'key': destination_key, 'album': album})


    return jsonify({'url': public_url(destination_key), 'filename': filename, 'key': destination_key, 'album': album})

@app.route('/kenangan')
def kenangan():
    return app.send_static_file('kenangan.html')


@app.route('/<path:path>')
def static_proxy(path):
    return app.send_static_file(path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
