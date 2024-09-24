from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import bcrypt
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import pydicom
from PIL import Image
from config import Config

patient_bp = Blueprint('patient', __name__)



@patient_bp.route('/patient/patient_signup', methods=['GET', 'POST'])
def patient_signup():
    if request.method == 'POST':
        name = request.form['name']
        phone_number = request.form['phone_number']
        add = request.form['add']
        sex = request.form['sex']
        age =request.form['age']
        email = request.form['email']
        password = request.form['password']
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert into MySQL
        cur = current_app.config['MYSQL'].connection.cursor()
        cur.execute("INSERT INTO patient (name,ph_no,email,address,sex,password,age) VALUES (%s, %s, %s, %s, %s,%s,%s)", (name, phone_number,email,add,sex,hashed_password,age))
        current_app.config['MYSQL'].connection.commit()
        cur.close()
        
        flash('Your account has been created!', 'success')
        return redirect(url_for('patient.patient_login'))
    
    return render_template('Patient/pt_signup.html')



@patient_bp.route('/patient/patient_login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        # Get user input from the form
        username = request.form['username']
        password = request.form['password']

        # Connect to the database and create a cursor
        cur = current_app.config['MYSQL'].connection.cursor()
        
        try:
            # Execute query to get the hashed password for the given email
            cur.execute("SELECT password FROM patient WHERE email = %s", (username,))
            patient_data = cur.fetchone()

            if patient_data and bcrypt.checkpw(password.encode('utf-8'), patient_data[0].encode('utf-8')):
                # Store the username in the session
                session['username'] = username
                return redirect(url_for('patient.patient_dashboard'))
            else:
                flash("Login failed. Please check your credentials.", "error")
                return redirect(url_for('patient.patient_login'))
        except Exception as e:
            # Handle any exceptions that occur
            flash("An error occurred while processing your request.", "error")
            return redirect(url_for('patient.patient_login'))
        finally:
            # Ensure the cursor is closed even if an exception occurs
            current_app.config['MYSQL'].connection.commit()
            cur.close()
    
    return render_template('Patient/pt_login.html')


@patient_bp.route('/patient/patient_dashboard', methods=['GET', 'POST'])
def patient_dashboard():
    if 'username' not in session:
        flash("You are not logged in!", "error")
        return redirect(url_for('patient.patient_login'))

    u_id = session['username']

    cur = current_app.config['MYSQL'].connection.cursor()

    # Fetch patient data
    cur.execute("SELECT name, sex, age, email, p_id FROM patient WHERE email = %s", (u_id,))
    patient_data = cur.fetchone()

    if not patient_data:
        cur.close()
        flash("User data not found!", "error")
        return redirect(url_for('patient.patient_login'))

    # Fetch approved doctors' data
    cur.execute("SELECT d_id, name, email, specialization FROM doctor WHERE status = 'Approved'")
    approved_doctors = cur.fetchall()

    if request.method == 'POST':
        # Handle payment submission
        amount = request.form['amount']
        doctor_id = request.form['doctor_id']  

        # Handle file upload
        image = request.files.get('image')
        if image and Config.allowed_file(image.filename):
            filename = secure_filename(image.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image.save(file_path)
        else:
            file_path = None

        # Get current date
        payment_date = datetime.now()

        # Insert payment record into the database
        cur.execute("""
            INSERT INTO payment (payment_date, amount, pay_status, image, patient_id, doctor_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (payment_date, amount, 'unpaid', file_path, patient_data[4], doctor_id))
        

        flash("Payment recorded successfully!", "success")
        return redirect(url_for('patient.patient_dashboard'))
    current_app.config['MYSQL'].connection.commit()
    cur.close()

    return render_template('Patient/Patient-dashboard.html', 
                           patient_data=patient_data, 
                           approved_doctors=approved_doctors)

@patient_bp.route('/patient/payment_success')
def payment_success():
    return "Payment was successful!"


@patient_bp.route('/patient/logout_pt')
def pt_logout():
    if 'username' in session:
        session.pop('pusername', None)  # Remove the 'username' key from the session
    return render_template('home.html')




@patient_bp.route('/patient/sub_img', methods=['POST'])
def sub_img():
    if request.method == 'POST':
        p_id = request.form['p_id']
        name = request.form['name']
        age = request.form['age']
        
        # Check if an X-ray file is present in the request
        if 'x_ray' in request.files:
            x_ray = request.files['x_ray']
            if Config.allowed_file(x_ray.filename):
                # Generate a filename based on patient ID, name, and age
                filename = f"{p_id}_{name}_{age}"

                # Check if the file is a DICOM file
                if x_ray.filename.lower().endswith('.dcm'):
                    dicom_image = pydicom.dcmread(x_ray)

                    # Convert DICOM to JPEG
                    jpg_image = Image.fromarray(dicom_image.pixel_array)

                    # Save the JPEG file
                    filename = secure_filename(f"{filename}.jpg")
                    jpg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    jpg_image.save(jpg_path)
                else:
                    # For other image formats, save as is
                    filename = secure_filename(f"{filename}.{x_ray.filename.rsplit('.', 1)[1].lower()}")
                    jpg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    x_ray.save(jpg_path)

                # Replace backslashes with forward slashes
                jpg_path = jpg_path.replace('\\', '/')

                # Save the file path to the MySQL database
                cur = current_app.config['MYSQL'].connection.cursor()
                cur.execute("INSERT INTO x_ray_analysis (patient_id, x_ray_image) VALUES (%s, %s)", (p_id, jpg_path))
                current_app.config['MYSQL'].connection.commit()
                cur.close()

                flash('Image uploaded and data saved successfully!', 'success')
                return redirect(url_for('patient.patient_dashboard'))
            else:
                flash("Invalid file format.", "error")
                return redirect(url_for('patient.patient_dashboard'))
        else:
            flash("No file selected.", "error")
            return redirect(url_for('patient.patient_dashboard'))
    else:
        flash("You are not logged in.", "error")
        return redirect(url_for('patient.patient_dashboard'))
    
        

@patient_bp.route('/patient/view_image/<int:patient_id>')
def view_image(patient_id):
    if 'username' in session:
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p.p_id, p.name, p.sex, p.age, p.ph_no, r.r_image
            FROM patient p
            LEFT JOIN report r ON p.p_id = r.p_id
            WHERE p.p_id = %s
        """, (patient_id,))
        patient_data = cur.fetchone()
        cur.close()

        if patient_data:
            p_id, name, sex, age, ph_no, x_ray_image = patient_data
            return render_template('view_image.html', 
                                   pid=p_id, 
                                   full_name=name, 
                                   phone_number=ph_no, 
                                   gender=sex, 
                                   age=age, 
                                   image_url=x_ray_image)
        else:
            flash("Patient not found.", "error")
            return redirect(url_for('doctor_dashboard'))
    else:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('doctor_login'))
    

@patient_bp.route('/patient/view_report/<int:patient_id>')
def view_report(patient_id):
    if 'username' in session:
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p.p_id, p.name, p.sex, p.age, p.ph_no, r.r_image
            FROM patient p
            LEFT JOIN report r ON p.p_id = r.p_id
            WHERE p.p_id = %s
        """, (patient_id,))
        patient_data = cur.fetchone()
        cur.close()

        if patient_data:
            p_id, name, sex, age, ph_no, x_ray_image = patient_data
            return render_template('Report_template.html', 
                                   pid=p_id, 
                                   full_name=name, 
                                   phone_number=ph_no, 
                                   gender=sex, 
                                   age=age, 
                                   image_url=x_ray_image)
        else:
            flash("Patient not found.", "error")
            return redirect(url_for('doctor_dashboard'))
    else:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('doctor_login'))

