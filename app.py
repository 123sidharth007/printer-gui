from flask import Flask, request, render_template, redirect, url_for
import razorpay
import os
from PyPDF2 import PdfReader
import requests

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ORDER_FILES'] = {}  # Store order_id to filename mapping

# Razorpay setup (replace with your test keys)
razorpay_client = razorpay.Client(auth=("rzp_test_RG9lbxm3vi0JVH", "csWpoDM8sl3DLubjjge3XlI8"))

# Linux machine endpoint (replace with actual ngrok/public URL of Linux server)
LINUX_PRINT_URL = "https://johana-reputationless-luanna.ngrok-free.dev/print"  

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return render_template('index.html', error="No file uploaded")

    file = request.files['file']
    if file.filename == '':
        return render_template('index.html', error="No file selected")

    # ✅ Simpler: check extension instead of python-magic
    if file.filename.lower().endswith('.pdf'):
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        # Count PDF pages
        pdf = PdfReader(filename)
        page_count = len(pdf.pages)
        cost = page_count * 1  # ₹0.10 per page (set your own pricing)

        # Create Razorpay order
        order = razorpay_client.order.create({
            'amount': int(cost * 100),  # amount in paisa
            'currency': 'INR',
            'payment_capture': 1
        })
        order_id = order['id']
        app.config['ORDER_FILES'][order_id] = filename

        return render_template('payment.html', 
                               order_id=order_id, 
                               cost=cost, 
                               key_id="rzp_test_RG9lbxm3vi0JVH")  # your Razorpay key ID

    return render_template('index.html', error="Invalid file format. Please upload a PDF.")

@app.route('/payment_success/<order_id>')
def payment_success(order_id):
    try:
        payment = razorpay_client.order.payments(order_id)
        if payment['items']:
            filename = app.config['ORDER_FILES'].get(order_id)
            if not filename:
                return render_template('index.html', error="File not found")

            # Send PDF to Linux machine
            try:
                with open(filename, 'rb') as f:
                    response = requests.post(LINUX_PRINT_URL, files={'file': f})

                if response.status_code == 200:
                    os.remove(filename)  # delete file after sending
                    del app.config['ORDER_FILES'][order_id]
                    return render_template('success.html')
                else:
                    return render_template('index.html', error="  printer is offline")

            except requests.RequestException:
                return render_template('index.html', error="printer is not reachable")

        return render_template('index.html', error="Payment failed")
    except Exception as e:
        return render_template('index.html', error=f"Payment verification failed: {str(e)}")

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(debug=True, host='0.0.0.0')
