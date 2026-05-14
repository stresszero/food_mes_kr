import io
import base64

import pyqrcode


def get_qr_png(value, scale=6):
    """Print Format Jinja에서 사용. 값을 QR 코드 PNG로 변환해 base64 문자열 반환."""
    qr = pyqrcode.create(str(value))
    buf = io.BytesIO()
    qr.png(buf, scale=scale)
    return base64.b64encode(buf.getvalue()).decode()
