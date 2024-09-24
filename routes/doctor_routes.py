from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime
import bcrypt



doctor_bp = Blueprint('doctor', __name__)



@doctor_bp.route('/doctor/doctor_signup', methods=['GET', 'POST'])
def doctor_signup():
    if request.method == 'POST':
        name = request.form['name']
        phone_number = request.form['phone_number']
        specialization = request.form['specialization']
        license_no = request.form['license_no']
        email = request.form['email']
        password = request.form['password']
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cur = current_app.config['MYSQL'].connection.cursor()
        cur.execute("""
            INSERT INTO doctor (name, ph_no, specialization, license_no, email, hashed_password, status, is_approved) 
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', '0')
        """, (name, phone_number, specialization, license_no, email, hashed_password))
        current_app.config['MYSQL'].connection.commit()
        cur.close()
        
        flash('Your account has been created! Please wait for approval.', 'success')
        return redirect(url_for('doctor.doctor_login'))
    
    return render_template('Doctor/dr_Signup.html')



@doctor_bp.route('/doctor/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Get a cursor for database operations
        cur = current_app.config['MYSQL'].connection.cursor()
        
        # Fetch the doctor's data based on the email
        cur.execute("SELECT d_id, name, hashed_password, is_approved FROM doctor WHERE email = %s", (email,))
        doctor_data = cur.fetchone()
        
        # Commit and close the database connection
        current_app.config['MYSQL'].connection.commit()
        cur.close()

        # Check if doctor data is found and the password matches
        if doctor_data and bcrypt.checkpw(password.encode('utf-8'), doctor_data[2].encode('utf-8')):
            # Check if the account is approved
            if doctor_data[3] == '1':  
                session['d_id'] = doctor_data[0]  # Store d_id in session instead of email
                return redirect(url_for('doctor.doctor_dashboard'))
            else:
                flash("Your account is pending and needs approval from admin.", "warning")
                return redirect(url_for('doctor.doctor_login'))
        else:
            flash("Login failed. Please check your credentials.", "error")
            return redirect(url_for('doctor.doctor_login'))
    
    # Render the login template for GET requests
    return render_template('Doctor/dr_login.html')




@doctor_bp.route('/doctor/doctor_dashboard')
def doctor_dashboard():
    # Check if the user is logged in by checking 'd_id' in session
    if 'd_id' not in session:
        flash("You must be logged in to access the dashboard.", "error")
        return redirect(url_for('doctor.doctor_login'))

    d_id = session['d_id']  # Get the logged-in doctor's ID from the session
    cur = current_app.config['MYSQL'].connection.cursor()

    try:
        # Fetch doctor's details using the d_id
        cur.execute("SELECT d_id, name, specialization FROM doctor WHERE d_id = %s", (d_id,))
        doctor_data = cur.fetchone()

        if not doctor_data:
            flash("Doctor data not found!", "error")
            return redirect(url_for('doctor.doctor_login'))

        # Get the count of pending payments specific to the doctor (using d_id directly)
        cur.execute("SELECT COUNT(*) FROM payment WHERE doctor_id = %s AND pay_status = 'unpaid'", (d_id,))
        pending_count = cur.fetchone()[0]

        # Fetch pending payments for this doctor using doctor ID (d_id directly)
        cur.execute("""
        SELECT p.pay_id AS pay_id, p.payment_date AS payment_date, p.amount AS amount, p.image AS image, pt.name AS patient_name
        FROM payment p
        JOIN patient pt ON p.patient_id = pt.p_id
        WHERE p.doctor_id = %s AND p.pay_status = 'unpaid'
        """, (d_id,))
        pending_patient = cur.fetchall()

        # Fetch patients with a 'paid' status and their x-ray analysis and pending reports (using d_id directly)
        cur.execute("""
            SELECT 
                -- All columns from the patient table
                pt.p_id, pt.name, pt.email, pt.address, pt.sex, pt.age, pt.ph_no,
                
                -- All columns from the payment table
                p.pay_id, p.payment_date, p.amount, p.pay_status, p.image, p.patient_id AS payment_patient_id, p.doctor_id AS payment_doctor_id
                
            FROM 
                patient pt
            JOIN 
                payment p ON pt.p_id = p.patient_id
                
            WHERE 
                p.doctor_id = %s  -- Filter for the logged-in doctor
                AND p.pay_status = 'paid'  -- Only show patients with completed payments
        """, (d_id,))

        paid_patients = cur.fetchall()

        cur.close()

        # Render the dashboard template with context data
        return render_template(
            'Doctor/Doctor-dashboard.html',
            doctor_data=doctor_data,
            pending_count=pending_count,
            pending_patient=pending_patient,
            paid_patients=paid_patients
        )
    except Exception as e:
        cur.close()
        flash("An error occurred while fetching the dashboard data: " + str(e), "error")
        return redirect(url_for('doctor.doctor_login'))



@doctor_bp.route('/doctor/approve_payment/<int:pay_id>', methods=['POST'])
def approve_payment(pay_id):
    # Check if 'd_id' is in session instead of 'email'
    if 'd_id' not in session:
        flash("You are not logged in!", "error")
        return redirect(url_for('doctor.doctor_login'))
    
    # Get the doctor's decision from the form ('yes' = approve, 'no' = reject)
    decision = request.form.get('approve')  

    # Set the payment status based on the decision
    if decision == 'yes':
        pay_status = 'paid'  # Payment approved
    elif decision == 'no':
        pay_status = 'rejected'  # Payment rejected
    else:
        flash("Invalid action!", "error")
        return redirect(url_for('doctor.doctor_dashboard'))

    cur = current_app.config['MYSQL'].connection.cursor()

    try:
        # Get the doctor ID directly from the session
        doctor_id = session['d_id']

        # Verify that the payment belongs to the doctor
        cur.execute("SELECT doctor_id FROM payment WHERE pay_id = %s", (pay_id,))
        payment_data = cur.fetchone()

        if not payment_data or payment_data[0] != doctor_id:
            flash("Unauthorized action or payment not found!", "error")
            return redirect(url_for('doctor.doctor_dashboard'))

        # Update the payment status in the database
        cur.execute("UPDATE payment SET pay_status = %s WHERE pay_id = %s", (pay_status, pay_id))
        current_app.config['MYSQL'].connection.commit()

        flash("Payment status updated successfully!", "success")
    except Exception as e:
        current_app.config['MYSQL'].connection.rollback()  # Rollback in case of error
        flash("An error occurred while updating the payment status: " + str(e), "error")
    finally:
        cur.close()

    return redirect(url_for('doctor.doctor_dashboard'))


@doctor_bp.route('/doctor/patient-pending')
def doctor_pending():
    # Check if 'd_id' is in session instead of 'email'
    if 'd_id' not in session:
        flash('You must be logged in as a doctor to view this page.', 'error')
        return redirect(url_for('doctor.doctor_login'))

    cur = current_app.config['MYSQL'].connection.cursor()
    
    # Get the doctor ID directly from the session
    doctor_id = session['d_id']

    # Get the count of pending payments for this doctor
    cur.execute("SELECT COUNT(*) FROM payment WHERE doctor_id = %s AND pay_status = 'unpaid'", (doctor_id,))
    pending_count = cur.fetchone()[0]

    # Get the list of pending payments for this doctor
    cur.execute("""
        SELECT p.pay_id, p.payment_date, p.amount, p.image, pt.name AS patient_name
        FROM payment p
        JOIN patient pt ON p.patient_id = pt.p_id
        WHERE p.doctor_id = %s AND p.pay_status = 'unpaid'
    """, (doctor_id,))
    
    column_names = ['pay_id', 'payment_date', 'amount', 'image', 'patient_name']
    pending_patient = [dict(zip(column_names, row)) for row in cur.fetchall()]

    cur.close()

    return render_template('Doctor/patient-pending.html', pending_count=pending_count, pending_patient=pending_patient)



@doctor_bp.route('/doctor/generate_report/<int:patient_id>', methods=['GET', 'POST'])
def generate_report(patient_id):
    # Fetch patient details and X-ray information
    cur = current_app.config['MYSQL'].connection.cursor()
    cur.execute("""
        SELECT pt.p_id, pt.name AS patient_name, pt.age, pt.sex, pt.email, pt.ph_no, pt.address,
               x.study, x.technique, x.findings, x.impression, x.recommendations, x.summary, x.x_ray_image
        FROM patient pt
        JOIN x_ray_analysis x ON pt.p_id = x.patient_id
        WHERE pt.p_id = %s
    """, (patient_id,))
    patient_data = cur.fetchone()

    if request.method == 'POST':
        # Get the form data
        report_details = request.form.get('report_details')
        report_date = datetime.now()  # Capture the current date and time
        
        # Insert report data into the database
        cur.execute("""
            INSERT INTO report (patient_id, details, r_date, status) 
            VALUES (%s, %s, %s, 'pending')
        """, (patient_id, report_details, report_date))
        current_app.config['MYSQL'].connection.commit()

        flash('Report successfully generated.', 'success')
        return redirect(url_for('doctor.doctor_dashboard'))

    return render_template('Doctor/view_report.html', patient_data=patient_data)



@doctor_bp.route('/doctor/analyze_xray/<int:patient_id>', methods=['GET'])
def analyze_xray(patient_id):
    # Get the doctor ID from the session
    doctor_id = session.get('d_id')

    # Ensure the doctor is logged in
    if not doctor_id:
        flash("You must be logged in to access this page.", "error")
        return redirect(url_for('doctor.doctor_login'))  # Redirect to login if doctor is not logged in

    cur = current_app.config['MYSQL'].connection.cursor()
    try:
        # Fetch patient and X-ray analysis data, ensuring the patient is associated with the logged-in doctor
        query = """
            SELECT 
                p.p_id, p.name, p.ph_no, p.age, p.sex, p.address, 
                x.x_ray_image, x.study, x.technique, x.findings, 
                x.impression, x.recommendations, x.summary, x.x_ray_analysis_date
            FROM 
                patient p
            JOIN 
                x_ray_analysis x ON p.p_id = x.patient_id
            JOIN 
                payment pay ON p.p_id = pay.patient_id
            WHERE 
                p.p_id = %s 
                AND pay.doctor_id = %s
                AND pay.pay_status = 'paid'
        """
        cur.execute(query, (patient_id, doctor_id))
        patient_data = cur.fetchone()

        # Check if the patient and X-ray analysis exist
        if not patient_data:
            flash("Patient or X-ray analysis not found, or you don't have access to this patient.", "error")
            return redirect(url_for('doctor.doctor_dashboard'))

        # Render the template with patient_data directly
        return render_template('Doctor/analyze_xray.html', patient_data=patient_data)
    
    except Exception as e:
        flash(f"An error occurred: {e}", "error")
        return redirect(url_for('doctor.doctor_dashboard'))
    
    finally:
        cur.close()



@doctor_bp.route('/doctor/logout_dr')
def dr_logout():
    if 'email' in session:
        session.pop('email', None)  # Remove the 'email' key from the session
    return redirect(url_for('doctor.doctor_login'))