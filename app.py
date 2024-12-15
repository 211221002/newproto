from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from pymongo import MongoClient
import bcrypt
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
from os.path import join, dirname
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from collections import defaultdict

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
app.secret_key = "rahasia"

client = MongoClient("mongodb+srv://test:test@cluster0.6znvghk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME =  os.environ.get("DB_NAME")
db = client["Cluster0"]
users_collection = db["user"]
barang_collection = db["barang"]
transaksi_collection = db["transaksi"]

# Variabel global untuk menyimpan ringkasan transaksi
transaction_summary = []

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Mencari pengguna berdasarkan email
        user = users_collection.find_one({"email": email})
        
        # Memeriksa apakah password benar
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            # Menyimpan seluruh data pengguna dalam sesi
            session['user_id'] = str(user['_id'])
            session['user'] = {'name': user['name'], 'email': user['email']}  # Menyimpan data pengguna di sesi
            return redirect(url_for('dashboard'))  # Redirect ke dashboard setelah login berhasil
        else:
            flash("Invalid email or password", "danger")
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Ambil data dari form
        nama = request.form['nama']
        email = request.form['email']
        phone = request.form['no_hp']
        business_name = request.form['nama_usaha']
        business_address = request.form['alamat_usaha']
        password = request.form['password']
        confirm_password = request.form['konfirmasi_password']
        
        # Validasi password
        if password != confirm_password:
            flash("Kata sandi tidak cocok", "danger")
            return render_template('register.html', nama=nama, email=email, phone=phone,
                                   business_name=business_name, business_address=business_address)
        
        # Cek apakah email sudah terdaftar
        if users_collection.find_one({"email": email}):
            flash("Email sudah terdaftar", "danger")
            return render_template('register.html', nama=nama, email=email, phone=phone,
                                   business_name=business_name, business_address=business_address)

        # Hash kata sandi
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Simpan data pengguna ke MongoDB
        users_collection.insert_one({
            "name": nama,
            "email": email,
            "phone": phone,
            "business_name": business_name,
            "business_address": business_address,
            "password": hashed_password
        })
        flash("Registrasi berhasil, silakan masuk", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect ke login jika belum login
    
    # Ambil data pengguna yang sedang login
    user_id = session['user_id']
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    
    if user:
        # Tampilkan halaman Dashboard
        return render_template('dashboard.html', user=user)
    else:
        return redirect(url_for('login'))
    
@app.route('/logout')
def logout():
    # Hapus session yang ada
    session.pop('user_id', None)
    flash("Anda berhasil logout", "success")
    return redirect(url_for('login'))  # Redirect ke halaman login setelah logout

@app.route("/kasir", methods=["GET", "POST"])
def kasir():
    user = session.get('user')  # Assuming the user data is stored in session

    if not user:
        return redirect(url_for('login'))

    # Fetch data from the 'barang' collection
    barang_collection = db["barang"]
    items = barang_collection.find({}, {"item_name": 1, "sale_price": 1, "_id": 0})
    item_names_and_prices = [(item['item_name'], item['sale_price']) for item in items]

    # Initialize the summary of the transaction
    transaction_summary = []
    total_amount = 0
    payment_received = 0

    if request.method == "POST":
        # Handle transaction processing
        selected_item = request.form.get("nama_barang")
        harga_barang = request.form.get("harga_barang")
        jumlah_barang = request.form.get("jumlah_barang")
        uang_pembayaran = request.form.get("uang_pembayaran")

        # Ensure that the form fields are not empty or None
        if not selected_item or not harga_barang or not jumlah_barang or not uang_pembayaran:
            return render_template("kasir.html", error="Semua field harus diisi!", user=user, 
                                   item_names_and_prices=item_names_and_prices, transaction_summary=transaction_summary)

        try:
            harga_barang = float(harga_barang)
            jumlah_barang = int(jumlah_barang)
            uang_pembayaran = float(uang_pembayaran)
        except ValueError:
            return render_template("kasir.html", error="Masukkan nilai yang valid!", user=user, 
                                   item_names_and_prices=item_names_and_prices, transaction_summary=transaction_summary)

        # Add the transaction details to the summary
        total_item_price = harga_barang * jumlah_barang
        transaction_summary.append({
            "item_name": selected_item,
            "harga_barang": harga_barang,
            "jumlah_barang": jumlah_barang,
            "total_item_price": total_item_price
        })

        # Calculate the total amount of the transaction
        total_amount = sum(item['total_item_price'] for item in transaction_summary)
        
        # Update the payment received
        payment_received = uang_pembayaran

    return render_template("kasir.html", user=user, item_names_and_prices=item_names_and_prices, 
                           transaction_summary=transaction_summary, total_amount=total_amount, 
                           payment_received=payment_received)


@app.route('/gudang', methods=['GET'])
def gudang():
    # Pastikan pengguna sudah login
    if 'user_id' not in session:
        flash('Anda harus login terlebih dahulu', 'danger')
        return redirect(url_for('login'))

    # Ambil data pengguna dari sesi
    user = session.get('user')

    # Ambil data barang dari koleksi MongoDB dan urutkan berdasarkan 'quantity' secara menaik
    barang = barang_collection.find().sort('quantity', 1)  # 1 untuk urutan menaik
    
    # Ubah hasil query menjadi list untuk diteruskan ke template
    barang_list = list(barang)

    return render_template('gudang.html', user=user, barang_list=barang_list)


@app.route('/pembukuan', methods=['GET', 'POST'])
def pembukuan():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Get the logged-in user's information
    user_id = session['user_id']
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if user:
        # Fetch transactions from MongoDB
        transactions = list(transaksi_collection.find())

        # Format each transaction data for the template
        for transaction in transactions:
            # Check if tanggal is already a datetime object
            if isinstance(transaction['tanggal'], datetime):
                # If it's already a datetime object, convert to string
                transaction['tanggal'] = transaction['tanggal'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                # Otherwise, convert it from timestamp if necessary
                transaction['tanggal'] = datetime.fromtimestamp(transaction['tanggal']['$date']['$numberLong'] / 1000).strftime('%Y-%m-%d %H:%M:%S')

            # Directly convert to float or int without subscripting
            transaction['total_amount'] = int(transaction['total_amount'])  # Or float(transaction['total_amount']) if needed
            transaction['uang_pembayaran'] = int(transaction['uang_pembayaran'])  # Or float(transaction['uang_pembayaran']) if needed
            transaction['kembalian'] = int(transaction['kembalian'])  # Or float(transaction['kembalian']) if needed

            # Ensure each item in transaksi_data is displayed correctly
            for item in transaction['transaksi_data']:
                item['harga_barang'] = float(item['harga_barang'])
                item['total_item_price'] = float(item['total_item_price'])

        # Pass transactions to the template
        return render_template('pembukuan.html', user=user, transactions=transactions)
    else:
        return redirect(url_for('login'))


@app.route('/input_barang', methods=['GET', 'POST'])
def input_barang():
    # Pastikan pengguna sudah login dengan memeriksa sesi
    if 'user_id' not in session:
        flash('Anda harus login terlebih dahulu', 'danger')
        return redirect(url_for('login'))  # Redirect ke halaman login jika belum login

    # Ambil data pengguna dari sesi
    user = session.get('user')  # Mendapatkan data user dari sesi

    # Jika tidak ada data pengguna di sesi
    if not user:
        flash('Data pengguna tidak ditemukan. Pastikan Anda sudah login.', 'danger')
        return redirect(url_for('login'))  # Redirect ke halaman login jika data tidak ditemukan

    if request.method == 'POST':
        try:
            # Ambil data dari form
            item_name = request.form['item_name']
            purchase_price = int(request.form['purchase_price'])
            sale_price = int(request.form['selling_price'])
            quantity = int(request.form['quantity'])
            supplier_name = request.form['supplier_name']
            supplier_address = request.form['supplier_address']
            supplier_phone = request.form['supplier_phone']
            
            # Data untuk disimpan ke MongoDB
            item_data = {
                'item_name': item_name,
                'purchase_price': purchase_price,
                'sale_price': sale_price,
                'quantity': quantity,
                'supplier_name': supplier_name,
                'supplier_address': supplier_address,
                'supplier_phone': supplier_phone,
                'created_by': user['name'],  # Menyimpan nama user yang menambahkan barang
            }
            
            # Simpan data ke MongoDB
            barang_collection.insert_one(item_data)
            flash('Barang berhasil ditambahkan!', 'success')
            return redirect(url_for('input_barang'))  # Redirect setelah berhasil menyimpan

        except KeyError as e:
            flash(f'Missing field: {str(e)}', 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')

    return render_template('input_barang.html', user=user)  # Pass data user ke template

@app.route('/update_barang/<barang_id>', methods=['GET', 'POST'])
def update_barang(barang_id):
    if request.method == 'POST':
        # Get the data from the form
        item_name = request.form['item_name']
        try:
            purchase_price = int(request.form['purchase_price'])  # Convert to integer
            sale_price = int(request.form['sale_price'])          # Convert to integer
            quantity = int(request.form['quantity'])              # Convert to integer
        except ValueError:
            flash('Harga beli, harga jual, dan jumlah harus berupa angka.', 'danger')
            return redirect(url_for('update_barang', barang_id=barang_id))  # Stay on the same page if invalid input
        supplier_name = request.form['supplier_name']
        supplier_address = request.form['supplier_address']
        supplier_phone = request.form['supplier_phone']

        # Update the database
        barang_collection.update_one(
            {'_id': ObjectId(barang_id)},
            {'$set': {
                'item_name': item_name,
                'purchase_price': purchase_price,
                'sale_price': sale_price,
                'quantity': quantity,
                'supplier_name': supplier_name,
                'supplier_address': supplier_address,
                'supplier_phone': supplier_phone
            }}
        )

        flash('Barang updated successfully!', 'success')
        return redirect(url_for('gudang'))
    else:
        # Handle GET request (display edit form)
        barang = barang_collection.find_one({'_id': ObjectId(barang_id)})
        return render_template('edit_barang.html', barang=barang)


@app.route('/delete_barang/<barang_id>', methods=['POST'])
def delete_barang(barang_id):
    # Find the barang by ID and delete it
    barang = db.barang.find_one({'_id': ObjectId(barang_id)})
    if barang:
        db.barang.delete_one({'_id': ObjectId(barang_id)})
        flash('Barang berhasil dihapus', 'success')
    else:
        flash('Barang tidak ditemukan', 'danger')
    return redirect(url_for('gudang'))

@app.route('/get_price/<item_name>')
def get_price(item_name):
    # Cari barang berdasarkan item_name
    barang = barang_collection.find_one({"item_name": item_name})
    if barang:
        return jsonify({"sale_price": barang['sale_price']})
    else:
        return jsonify({"sale_price": 0})

@app.route('/kasir/selesaikan-transaksi', methods=['POST'])
def selesaikan_transaksi():
    try:
        # Ambil data dari form
        item_names = request.form.getlist('item_name[]')
        harga_barang = request.form.getlist('harga_barang[]')
        jumlah_barang = request.form.getlist('jumlah_barang[]')
        total_item_price = request.form.getlist('total_item_price[]')

        # Ambil data pembayaran
        uang_pembayaran = float(request.form['uang_pembayaran'])

        # Hitung total transaksi
        total_amount = sum(float(price) for price in total_item_price)

        # Hitung kembalian
        kembalian = uang_pembayaran - total_amount

        # Simpan data transaksi
        transaksi_data = []
        for i in range(len(item_names)):
            transaksi_data.append({
                'item_name': item_names[i],
                'harga_barang': float(harga_barang[i]),
                'jumlah_barang': int(jumlah_barang[i]),
                'total_item_price': float(total_item_price[i])
            })

        # Simpan transaksi ke database
        transaksi_collection.insert_one({
            'transaksi_data': transaksi_data,
            'total_amount': total_amount,
            'uang_pembayaran': uang_pembayaran,
            'kembalian': kembalian,
            'tanggal': datetime.now()
        })

        # Kurangi jumlah barang di barang_collection
        for i in range(len(item_names)):
            item_name = item_names[i]
            jumlah_dibeli = int(jumlah_barang[i])

            # Update quantity barang berdasarkan item_name
            barang = barang_collection.find_one({"item_name": item_name})
            if barang:
                new_quantity = barang.get('quantity', 0) - jumlah_dibeli
                if new_quantity < 0:
                    flash(f"Stok barang '{item_name}' tidak mencukupi!", "error")
                    return redirect(url_for('kasir'))
                barang_collection.update_one(
                    {"item_name": item_name},
                    {"$set": {"quantity": new_quantity}}
                )

        flash("Transaksi berhasil diselesaikan dan stok telah diperbarui!", "success")
        return redirect(url_for('kasir'))
    except Exception as e:
        print(f"Error during transaction: {e}")
        flash("Terjadi kesalahan saat menyelesaikan transaksi.", "error")
        return redirect(url_for('kasir'))

@app.route('/back_to_dashboard')
def back_to_dashboard():
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)