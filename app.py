import streamlit as st
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, date, timedelta
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from sklearn.ensemble import IsolationForest
import numpy as np
import streamlit_authenticator as stauth
import hashlib
import cv2
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

# Load environment variables
load_dotenv()

# Initialize MongoDB client
mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("DB_NAME")

client = MongoClient(mongo_uri)
db = client[db_name]
employees_col = db["employees"]
attendance_col = db["attendance"]
users_col = db["users"]
leaves_col = db["leaves"]
face_embeddings_col = db["face_embeddings"]

# Initialize face recognition models
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
mtcnn = MTCNN(keep_all=True, device=device)
resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)

# Streamlit App Configuration
st.set_page_config(page_title="Employee Attendance System", layout="wide")
st.title("📋 Employee Attendance System with AI")

# Initialize session states
if 'add_form_key' not in st.session_state:
    st.session_state.add_form_key = 0
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# Helper Functions
def send_email(to_email, subject, body):
    """Send email notification"""
    try:
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
        msg = MIMEMultipart()
        msg['From'] = smtp_username
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Error sending email: {e}")
        return False

def detect_attendance_anomalies(employee_id):
    """Use Isolation Forest to detect attendance anomalies"""
    # Get employee's attendance history
    records = list(attendance_col.find({"employees.employeeId": employee_id}))
    
    if len(records) < 10:  # Need sufficient data
        return None
    
    # Prepare data for anomaly detection
    data = []
    for record in records:
        for emp_record in record["employees"]:
            if emp_record["employeeId"] == employee_id:
                status = 1 if emp_record["status"] in ["Present", "Late"] else 0
                check_in = emp_record.get("checkIn", "00:00")
                check_out = emp_record.get("checkOut", "00:00")
                
                # Convert time to minutes since midnight
                def time_to_minutes(t):
                    h, m = map(int, t.split(':'))
                    return h * 60 + m
                
                in_min = time_to_minutes(check_in)
                out_min = time_to_minutes(check_out)
                work_duration = out_min - in_min if out_min > in_min else 0
                
                data.append([status, in_min, work_duration])
    
    # Train anomaly detection model
    clf = IsolationForest(contamination=0.1)
    preds = clf.fit_predict(data)
    anomalies = [i for i, x in enumerate(preds) if x == -1]
    
    return anomalies if anomalies else None

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed_password):
    """Verify password against hashed password"""
    return hash_password(password) == hashed_password

def create_user(username, password, role):
    """Create a new user with hashed password"""
    if users_col.find_one({"username": username}):
        return False, "Username already exists"
    
    hashed_password = hash_password(password)
    users_col.insert_one({
        "username": username,
        "password": hashed_password,
        "role": role,
        "created_at": datetime.now()
    })
    return True, "User created successfully"

def authenticate_user(username, password):
    """Authenticate user and return role if successful"""
    user = users_col.find_one({"username": username})
    if user and verify_password(password, user["password"]):
        return True, user["role"], user
    return False, None, None

def login_page():
    """Display login page and handle authentication"""
    st.title("🔐 Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                success, role, user = authenticate_user(username, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user_role = role
                    st.session_state.current_user = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    # Add admin registration form
    if not users_col.find_one({"role": "admin"}):
        st.markdown("---")
        st.subheader("Create Admin Account")
        with st.form("admin_registration"):
            admin_username = st.text_input("Admin Username")
            admin_password = st.text_input("Admin Password", type="password")
            admin_confirm = st.text_input("Confirm Password", type="password")
            submit_admin = st.form_submit_button("Create Admin")
            
            if submit_admin:
                if not all([admin_username, admin_password, admin_confirm]):
                    st.error("Please fill all fields")
                elif admin_password != admin_confirm:
                    st.error("Passwords do not match")
                else:
                    success, message = create_user(admin_username, admin_password, "admin")
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

def logout():
    """Handle logout"""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.current_user = None
    st.rerun()

def get_face_embedding(image):
    """Get face embedding from image using FaceNet"""
    try:
        # Detect face
        boxes, _ = mtcnn.detect(image)
        if boxes is None:
            return None
        
        # Get face embedding
        face = mtcnn(image)
        if face is None:
            return None
            
        # Get embedding
        embedding = resnet(face.unsqueeze(0).to(device))
        return embedding.detach().cpu().numpy()
    except Exception as e:
        st.error(f"Error in face recognition: {e}")
        return None

def register_face(employee_id):
    """Register employee's face"""
    st.subheader("Register Face")
    st.info("Please look directly at the camera")
    
    # Initialize webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        st.error("Could not open webcam")
        return
    
    # Create a placeholder for the video feed
    video_placeholder = st.empty()
    
    # Capture button
    capture_button = st.button("Capture Face")
    captured = False
    
    while not captured:
        ret, frame = cap.read()
        if not ret:
            st.error("Failed to capture frame")
            break
            
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Display the frame
        video_placeholder.image(frame_rgb, channels="RGB")
        
        if capture_button:
            # Get face embedding
            embedding = get_face_embedding(frame_rgb)
            if embedding is not None:
                # Save embedding to database
                face_embeddings_col.update_one(
                    {"employeeId": employee_id},
                    {"$set": {
                        "embedding": embedding.tolist(),
                        "updated_at": datetime.now()
                    }},
                    upsert=True
                )
                st.success("Face registered successfully!")
                captured = True
            else:
                st.error("No face detected. Please try again.")
    
    cap.release()

def mark_attendance_by_face():
    """Mark attendance using face recognition"""
    st.subheader("Mark Attendance by Face")
    st.info("Please look directly at the camera")
    
    # Initialize webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        st.error("Could not open webcam")
        return
    
    # Create a placeholder for the video feed
    video_placeholder = st.empty()
    
    # Capture button
    capture_button = st.button("Mark Attendance")
    captured = False
    
    while not captured:
        ret, frame = cap.read()
        if not ret:
            st.error("Failed to capture frame")
            break
            
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Display the frame
        video_placeholder.image(frame_rgb, channels="RGB")
        
        if capture_button:
            # Get face embedding
            embedding = get_face_embedding(frame_rgb)
            if embedding is not None:
                # Find matching employee
                best_match = None
                best_distance = float('inf')
                
                for record in face_embeddings_col.find():
                    stored_embedding = np.array(record["embedding"])
                    distance = np.linalg.norm(embedding - stored_embedding)
                    if distance < best_distance:
                        best_distance = distance
                        best_match = record["employeeId"]
                
                if best_match and best_distance < 1.0:  # Threshold for face matching
                    # Mark attendance
                    today = date.today().strftime("%Y-%m-%d")
                    current_time = datetime.now().strftime("%H:%M")
                    
                    attendance_col.update_one(
                        {"date": today},
                        {"$push": {
                            "employees": {
                                "employeeId": best_match,
                                "status": "Present",
                                "checkIn": current_time,
                                "checkOut": None
                            }
                        }},
                        upsert=True
                    )
                    
                    employee = employees_col.find_one({"employeeId": best_match})
                    st.success(f"Attendance marked for {employee['empName']}!")
                    captured = True
                else:
                    st.error("No matching face found in database")
            else:
                st.error("No face detected. Please try again.")
    
    cap.release()

def apply_leave():
    """Employee leave application form"""
    st.subheader("Apply for Leave")
    
    with st.form("leave_form"):
        leave_type = st.selectbox("Leave Type", ["Sick Leave", "Casual Leave", "Earned Leave"])
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")
        reason = st.text_area("Reason for Leave")
        submit = st.form_submit_button("Submit Leave Application")
        
        if submit:
            if not all([leave_type, start_date, end_date, reason]):
                st.error("Please fill all fields")
            elif end_date < start_date:
                st.error("End date cannot be before start date")
            else:
                # Calculate number of days
                delta = end_date - start_date
                num_days = delta.days + 1
                
                # Create leave application
                leave_doc = {
                    "employeeId": st.session_state.current_user["employeeId"],
                    "leaveType": leave_type,
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                    "numDays": num_days,
                    "reason": reason,
                    "status": "Pending",
                    "appliedAt": datetime.now(),
                    "approvedBy": None,
                    "approvedAt": None
                }
                
                leaves_col.insert_one(leave_doc)
                st.success("Leave application submitted successfully!")

def manage_leaves():
    """Admin leave management interface"""
    st.subheader("Manage Leave Applications")
    
    # Get all leave applications
    leaves = list(leaves_col.find().sort("appliedAt", -1))
    
    if not leaves:
        st.info("No leave applications found")
    else:
        # Display leave applications
        for leave in leaves:
            with st.expander(f"Leave Application - {leave['employeeId']}"):
                employee = employees_col.find_one({"employeeId": leave["employeeId"]})
                st.write(f"**Employee:** {employee['empName']}")
                st.write(f"**Leave Type:** {leave['leaveType']}")
                st.write(f"**Start Date:** {leave['startDate']}")
                st.write(f"**End Date:** {leave['endDate']}")
                st.write(f"**Number of Days:** {leave['numDays']}")
                st.write(f"**Reason:** {leave['reason']}")
                st.write(f"**Status:** {leave['status']}")
                
                if leave['status'] == "Pending":
                    col1, col2 = st.columns(2)
                    if col1.button("Approve", key=f"approve_{leave['_id']}"):
                        leaves_col.update_one(
                            {"_id": leave["_id"]},
                            {"$set": {
                                "status": "Approved",
                                "approvedBy": st.session_state.current_user["username"],
                                "approvedAt": datetime.now()
                            }}
                        )
                        st.success("Leave application approved!")
                        st.rerun()
                    
                    if col2.button("Reject", key=f"reject_{leave['_id']}"):
                        leaves_col.update_one(
                            {"_id": leave["_id"]},
                            {"$set": {
                                "status": "Rejected",
                                "approvedBy": st.session_state.current_user["username"],
                                "approvedAt": datetime.now()
                            }}
                        )
                        st.error("Leave application rejected!")
                        st.rerun()

def view_my_leaves():
    """Employee view of their leave applications"""
    st.subheader("My Leave Applications")
    
    if st.session_state.user_role == "employee":
        leaves = list(leaves_col.find({
            "employeeId": st.session_state.current_user["employeeId"]
        }).sort("appliedAt", -1))
        
        if not leaves:
            st.info("No leave applications found")
        else:
            for leave in leaves:
                with st.expander(f"Leave Application - {leave['startDate']} to {leave['endDate']}"):
                    st.write(f"**Leave Type:** {leave['leaveType']}")
                    st.write(f"**Start Date:** {leave['startDate']}")
                    st.write(f"**End Date:** {leave['endDate']}")
                    st.write(f"**Number of Days:** {leave['numDays']}")
                    st.write(f"**Reason:** {leave['reason']}")
                    st.write(f"**Status:** {leave['status']}")
                    if leave['status'] != "Pending":
                        st.write(f"**Processed By:** {leave['approvedBy']}")
                        st.write(f"**Processed At:** {leave['approvedAt']}")

def generate_attendance_analytics():
    """Generate attendance analytics and visualizations"""
    st.subheader("Attendance Analytics")
    
    # Initialize session state for analytics if not exists
    if 'analytics_counter' not in st.session_state:
        st.session_state.analytics_counter = 0
    st.session_state.analytics_counter += 1
    
    # Date range selection
    col1, col2 = st.columns(2)
    start_date = col1.date_input(
        "Start Date", 
        date.today() - timedelta(days=30), 
        key=f"analytics_dashboard_start_date_{st.session_state.analytics_counter}"
    )
    end_date = col2.date_input(
        "End Date", 
        date.today(), 
        key=f"analytics_dashboard_end_date_{st.session_state.analytics_counter}"
    )
    
    # Store dates in session state
    st.session_state.analytics_start_date = start_date
    st.session_state.analytics_end_date = end_date
    
    # Get attendance data
    attendance_records = list(attendance_col.find({
        "date": {
            "$gte": start_date.strftime("%Y-%m-%d"),
            "$lte": end_date.strftime("%Y-%m-%d")
        }
    }))
    
    if not attendance_records:
        st.info("No attendance records found for the selected period")
        return
    
    # Process data for analytics
    attendance_data = []
    for record in attendance_records:
        for emp_record in record["employees"]:
            attendance_data.append({
                "Date": record["date"],
                "EmployeeID": emp_record["employeeId"],
                "Status": emp_record["status"],
                "CheckIn": emp_record.get("checkIn", "N/A"),
                "CheckOut": emp_record.get("checkOut", "N/A")
            })
    
    df = pd.DataFrame(attendance_data)
    
    # Display analytics
    st.write("### Attendance Overview")
    
    # Status distribution
    status_counts = df["Status"].value_counts()
    fig1 = px.pie(values=status_counts.values, names=status_counts.index, title="Attendance Status Distribution")
    st.plotly_chart(fig1, key=f"status_distribution_{st.session_state.analytics_counter}")
    
    # Daily attendance trend
    daily_counts = df.groupby(["Date", "Status"]).size().unstack().fillna(0)
    fig2 = px.line(daily_counts, title="Daily Attendance Trend")
    st.plotly_chart(fig2, key=f"daily_trend_{st.session_state.analytics_counter}")
    
    # Department-wise analysis
    dept_data = []
    for emp_id in df["EmployeeID"].unique():
        emp = employees_col.find_one({"employeeId": emp_id})
        if emp:
            dept_data.append({
                "EmployeeID": emp_id,
                "Department": emp["department"]
            })
    
    dept_df = pd.DataFrame(dept_data)
    merged_df = pd.merge(df, dept_df, on="EmployeeID")
    
    dept_status = merged_df.groupby(["Department", "Status"]).size().unstack().fillna(0)
    fig3 = px.bar(dept_status, title="Department-wise Attendance")
    st.plotly_chart(fig3, key=f"department_analysis_{st.session_state.analytics_counter}")

def generate_pdf_report(employee_id, start_date, end_date):
    """Generate PDF attendance report for an employee"""
    # Get employee details
    employee = employees_col.find_one({"employeeId": employee_id})
    if not employee:
        return None
    
    # Get attendance records
    attendance_records = list(attendance_col.find({
        "date": {
            "$gte": start_date.strftime("%Y-%m-%d"),
            "$lte": end_date.strftime("%Y-%m-%d")
        },
        "employees.employeeId": employee_id
    }))
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Add title
    title = Paragraph(f"Attendance Report for {employee['empName']}", styles['Title'])
    elements.append(title)
    
    # Add employee details
    elements.append(Paragraph(f"Employee ID: {employee_id}", styles['Normal']))
    elements.append(Paragraph(f"Department: {employee['department']}", styles['Normal']))
    elements.append(Paragraph(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", styles['Normal']))
    elements.append(Paragraph(" ", styles['Normal']))
    
    # Add attendance table
    if attendance_records:
        data = [["Date", "Status", "Check In", "Check Out"]]
        for record in attendance_records:
            for emp_record in record["employees"]:
                if emp_record["employeeId"] == employee_id:
                    data.append([
                        record["date"],
                        emp_record["status"],
                        emp_record.get("checkIn", "N/A"),
                        emp_record.get("checkOut", "N/A")
                    ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No attendance records found for the selected period.", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def download_attendance_report():
    """UI for downloading attendance reports"""
    st.subheader("Download Attendance Report")
    
    # Initialize session state for report if not exists
    if 'report_counter' not in st.session_state:
        st.session_state.report_counter = 0
    st.session_state.report_counter += 1
    
    # Employee selection
    all_employees = list(employees_col.find())
    employee_ids = [emp["employeeId"] for emp in all_employees]
    selected_employee = st.selectbox(
        "Select Employee", 
        employee_ids, 
        key=f"report_download_employee_{st.session_state.report_counter}"
    )
    
    # Date range selection
    col1, col2 = st.columns(2)
    start_date = col1.date_input(
        "Start Date", 
        date.today() - timedelta(days=30), 
        key=f"report_download_start_date_{st.session_state.report_counter}"
    )
    end_date = col2.date_input(
        "End Date", 
        date.today(), 
        key=f"report_download_end_date_{st.session_state.report_counter}"
    )
    
    if st.button("Generate Report", key=f"generate_report_{st.session_state.report_counter}"):
        pdf_buffer = generate_pdf_report(selected_employee, start_date, end_date)
        if pdf_buffer:
            employee = employees_col.find_one({"employeeId": selected_employee})
            st.download_button(
                label="Download PDF Report",
                data=pdf_buffer,
                file_name=f"attendance_report_{employee['empName']}_{start_date}_{end_date}.pdf",
                mime="application/pdf",
                key=f"download_report_{st.session_state.report_counter}"
            )
        else:
            st.error("Failed to generate report")

def check_missing_attendance():
    """Check for employees who haven't marked attendance today"""
    today = date.today().strftime("%Y-%m-%d")
    
    # Get today's attendance
    today_attendance = attendance_col.find_one({"date": today})
    if not today_attendance:
        return []
    
    # Get all employees
    all_employees = list(employees_col.find())
    
    # Find employees who haven't marked attendance
    missing_employees = []
    for emp in all_employees:
        found = False
        for emp_record in today_attendance["employees"]:
            if emp_record["employeeId"] == emp["employeeId"]:
                found = True
                break
        if not found:
            missing_employees.append(emp)
    
    return missing_employees

def send_reminder_emails():
    """Send reminder emails to employees who haven't marked attendance"""
    missing_employees = check_missing_attendance()
    
    if not missing_employees:
        st.info("All employees have marked attendance today")
        return
    
    st.warning(f"{len(missing_employees)} employees haven't marked attendance today")
    
    if st.button("Send Reminder Emails", key="send_reminders"):
        with st.spinner("Sending reminder emails..."):
            for emp in missing_employees:
                if emp.get("email"):
                    subject = "Reminder: Mark Your Attendance"
                    body = f"""Dear {emp['empName']},

This is a reminder that you haven't marked your attendance for today. Please log in to the system and mark your attendance as soon as possible.

Best regards,
Attendance System"""
                    
                    if send_email(emp["email"], subject, body):
                        st.success(f"Reminder sent to {emp['empName']}")
                    time.sleep(1)  # Rate limiting

def main():
    """Main application function"""
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Add logout button
    if st.sidebar.button("Logout", key="logout_button"):
        logout()
    
    # Show user info
    st.sidebar.write(f"Logged in as: {st.session_state.current_user['username']}")
    st.sidebar.write(f"Role: {st.session_state.user_role}")
    
    # Add auto reminder section to admin dashboard
    if st.session_state.user_role == "admin":
        st.sidebar.markdown("---")
        st.sidebar.subheader("Auto Reminders")
        send_reminder_emails()
    
    # Create tabs based on user role
    if st.session_state.user_role == "admin":
        tabs = st.tabs([
            "Dashboard",
            "Add Employee",
            "Mark Attendance",
            "View Attendance",
            "Reports",
            "Employee Management",
            "Leave Management",
            "Face Registration"
        ])
    else:
        tabs = st.tabs([
            "Dashboard",
            "Mark Attendance",
            "View Attendance",
            "My Leaves",
            "Face Registration"
        ])
    
    # Admin Dashboard
    if st.session_state.user_role == "admin":
        with tabs[0]:
            st.title("Admin Dashboard")
            generate_attendance_analytics()
            download_attendance_report()
    
    # Employee Dashboard
    else:
        with tabs[0]:
            st.title("Employee Dashboard")
            # Show employee's recent attendance
            recent_attendance = list(attendance_col.find({
                "employees.employeeId": st.session_state.current_user["employeeId"]
            }).sort("date", -1).limit(5))
            
            if recent_attendance:
                st.subheader("Recent Attendance")
                for record in recent_attendance:
                    for emp_record in record["employees"]:
                        if emp_record["employeeId"] == st.session_state.current_user["employeeId"]:
                            st.write(f"**Date:** {record['date']}")
                            st.write(f"**Status:** {emp_record['status']}")
                            st.write(f"**Check In:** {emp_record.get('checkIn', 'N/A')}")
                            st.write(f"**Check Out:** {emp_record.get('checkOut', 'N/A')}")
                            st.write("---")
    
    # Add Employee (Admin only)
    if st.session_state.user_role == "admin":
        with tabs[1]:
            st.header("👨‍💼 Add New Employee")
            with st.form(key=f"add_employee_form_{st.session_state.add_form_key}", clear_on_submit=True):
                cols = st.columns(2)
                emp_id = cols[0].text_input("Employee ID*")
                name = cols[1].text_input("Full Name*")
                email = cols[0].text_input("Email*")
                mobile = cols[1].text_input("Mobile Number*")
                department = st.selectbox("Department*", 
                                        ["HR", "IT", "Finance", "Operations", "Marketing"])
                position = st.selectbox("Position*", 
                                      ["Intern", "Junior", "Senior", "Manager", "Director"])
                
                if st.form_submit_button("Add Employee"):
                    if not all([emp_id, name, email, mobile, department, position]):
                        st.error("Please fill all required fields!")
                    else:
                        # Check if employee ID already exists
                        if employees_col.find_one({"employeeId": emp_id}):
                            st.error(f"Employee ID {emp_id} already exists!")
                        else:
                            document = {
                                "employeeId": emp_id,
                                "empName": name,
                                "email": email,
                                "mobile": mobile,
                                "department": department,
                                "position": position,
                                "joinDate": datetime.now().strftime("%Y-%m-%d")
                            }
                            try:
                                employees_col.insert_one(document)
                                st.success(f"Employee {name} added successfully!")
                                st.session_state.add_form_key += 1
                            except Exception as e:
                                st.error(f"Error adding employee: {e}")
    
    # Mark Attendance
    with tabs[1 if st.session_state.user_role == "admin" else 0]:
        st.header("🖊️ Mark Attendance")
        
        # Initialize session state for attendance if not exists
        if 'attendance_counter' not in st.session_state:
            st.session_state.attendance_counter = 0
        st.session_state.attendance_counter += 1
        
        # Face recognition attendance
        if st.checkbox(
            "Use Face Recognition", 
            key=f"mark_attendance_face_recognition_{st.session_state.attendance_counter}"
        ):
            mark_attendance_by_face()
        else:
            # Manual attendance marking
            attendance_date = st.date_input(
                "Select Date", 
                date.today(), 
                key=f"mark_attendance_manual_date_{st.session_state.attendance_counter}"
            )
            all_employees = list(employees_col.find())
            
            if not all_employees:
                st.warning("No employees found in the database.")
            else:
                existing_attendance = attendance_col.find_one({
                    "date": attendance_date.strftime("%Y-%m-%d")
                })
                
                if existing_attendance:
                    st.warning(f"Attendance already marked for {attendance_date.strftime('%Y-%m-%d')}")
                else:
                    # Manual attendance form
                    with st.form(key=f"manual_attendance_form_{st.session_state.attendance_counter}"):
                        attendance_records = []
                        for emp in all_employees:
                            status = st.selectbox(
                                f"Status for {emp['empName']}",
                                ["Present", "Absent", "Leave", "Late"],
                                key=f"status_{emp['employeeId']}"
                            )
                            attendance_records.append({
                                "employeeId": emp["employeeId"],
                                "status": status
                            })
                        
                        if st.form_submit_button("Submit Attendance"):
                            attendance_doc = {
                                "date": attendance_date.strftime("%Y-%m-%d"),
                                "markedAt": datetime.now(),
                                "employees": attendance_records
                            }
                            attendance_col.insert_one(attendance_doc)
                            st.success("Attendance marked successfully!")
    
    # View Attendance
    with tabs[2 if st.session_state.user_role == "admin" else 1]:
        st.header("📅 View Attendance Records")
        
        # Initialize session state for view if not exists
        if 'view_counter' not in st.session_state:
            st.session_state.view_counter = 0
        st.session_state.view_counter += 1
        
        # Date range selection
        col1, col2 = st.columns(2)
        start_date = col1.date_input(
            "Start Date", 
            date.today() - timedelta(days=30), 
            key=f"view_attendance_start_date_{st.session_state.view_counter}"
        )
        end_date = col2.date_input(
            "End Date", 
            date.today(), 
            key=f"view_attendance_end_date_{st.session_state.view_counter}"
        )
        
        # Employee filter (admin only)
        if st.session_state.user_role == "admin":
            all_employees = list(employees_col.find())
            employee_ids = [emp["employeeId"] for emp in all_employees]
            selected_employee = st.selectbox(
                "Filter by Employee (Optional)", 
                [None] + employee_ids, 
                key=f"view_attendance_employee_{st.session_state.view_counter}"
            )
        else:
            selected_employee = st.session_state.current_user["employeeId"]
        
        if st.button("Load Attendance", key="load_attendance"):
            query = {
                "date": {
                    "$gte": start_date.strftime("%Y-%m-%d"),
                    "$lte": end_date.strftime("%Y-%m-%d")
                }
            }
            
            if selected_employee:
                query["employees.employeeId"] = selected_employee
            
            attendance_records = list(attendance_col.find(query).sort("date", 1))
            
            if not attendance_records:
                st.info("No attendance records found for the selected criteria.")
            else:
                # Process and display data
                attendance_data = []
                
                for record in attendance_records:
                    for emp_record in record["employees"]:
                        if selected_employee and emp_record["employeeId"] != selected_employee:
                            continue
                            
                        emp = employees_col.find_one({"employeeId": emp_record["employeeId"]})
                        attendance_data.append({
                            "Date": record["date"],
                            "ID": emp_record["employeeId"],
                            "Name": emp["empName"],
                            "Department": emp["department"],
                            "Status": emp_record["status"],
                            "Check-in": emp_record.get("checkIn", "N/A"),
                            "Check-out": emp_record.get("checkOut", "N/A")
                        })
                
                df = pd.DataFrame(attendance_data)
                st.dataframe(df, use_container_width=True)
    
    # Reports (Admin only)
    if st.session_state.user_role == "admin":
        with tabs[4]:
            st.header("📈 Reports")
            generate_attendance_analytics()
            download_attendance_report()
    
    # Employee Management (Admin only)
    if st.session_state.user_role == "admin":
        with tabs[5]:
            st.header("👥 Employee Management")
            # View all employees
            st.subheader("All Employees")
            all_employees = list(employees_col.find())
            
            if not all_employees:
                st.info("No employees found in the database.")
            else:
                # Display employee table
                emp_data = []
                for emp in all_employees:
                    emp_data.append({
                        "ID": emp["employeeId"],
                        "Name": emp["empName"],
                        "Email": emp["email"],
                        "Mobile": emp["mobile"],
                        "Department": emp["department"],
                        "Position": emp["position"],
                        "Join Date": emp.get("joinDate", "N/A")
                    })
                
                st.dataframe(pd.DataFrame(emp_data), use_container_width=True)
            
            # Employee actions
            st.subheader("Employee Actions")
            action = st.radio("Select Action", ["Promote Employee", "Update Details", "Remove Employee"])
            
            if action == "Promote Employee":
                with st.form(key="promote_employee_form"):
                    emp_id = st.selectbox("Select Employee", employee_ids)
                    new_position = st.selectbox("New Position", 
                                              ["Intern", "Junior", "Senior", "Manager", "Director"])
                    
                    if st.form_submit_button("Promote"):
                        result = employees_col.update_one(
                            {"employeeId": emp_id},
                            {"$set": {"position": new_position}}
                        )
                        if result.modified_count > 0:
                            st.success(f"Employee {emp_id} promoted to {new_position}!")
                        else:
                            st.error("No changes made or employee not found")
            
            elif action == "Update Details":
                with st.form(key="update_employee_form"):
                    emp_id = st.selectbox("Select Employee", employee_ids)
                    emp = employees_col.find_one({"employeeId": emp_id})
                    
                    if emp:
                        new_email = st.text_input("Email", emp["email"])
                        new_mobile = st.text_input("Mobile", emp["mobile"])
                        new_department = st.selectbox("Department", 
                                                   ["HR", "IT", "Finance", "Operations", "Marketing"],
                                                   index=["HR", "IT", "Finance", "Operations", "Marketing"].index(emp["department"]))
                        
                        if st.form_submit_button("Update"):
                            update_data = {
                                "email": new_email,
                                "mobile": new_mobile,
                                "department": new_department
                            }
                            result = employees_col.update_one(
                                {"employeeId": emp_id},
                                {"$set": update_data}
                            )
                            if result.modified_count > 0:
                                st.success(f"Employee {emp_id} details updated!")
                            else:
                                st.error("No changes made or employee not found")
            
            elif action == "Remove Employee":
                with st.form(key="remove_employee_form"):
                    emp_id = st.selectbox("Select Employee to Remove", employee_ids)
                    
                    if st.form_submit_button("Remove"):
                        # Check if employee has attendance records
                        has_attendance = attendance_col.count_documents({
                            "employees.employeeId": emp_id
                        }) > 0
                        
                        if has_attendance:
                            st.warning("This employee has attendance records. Deleting will remove all associated data.")
                            confirm = st.checkbox("I understand and want to proceed", key="confirm_remove")
                            if not confirm:
                                st.stop()
                        
                        # Delete employee and their attendance records
                        employees_col.delete_one({"employeeId": emp_id})
                        attendance_col.update_many(
                            {},
                            {"$pull": {"employees": {"employeeId": emp_id}}}
                        )
                        st.success(f"Employee {emp_id} removed successfully!")
    
    # Leave Management
    if st.session_state.user_role == "admin":
        with tabs[6]:
            st.header("📝 Leave Management")
            manage_leaves()
    else:
        with tabs[3]:
            st.header("📝 My Leaves")
            apply_leave()
            view_my_leaves()
    
    # Face Registration
    with tabs[-1]:
        st.header("📸 Face Registration")
        if st.session_state.user_role == "admin":
            all_employees = list(employees_col.find())
            employee_ids = [emp["employeeId"] for emp in all_employees]
            selected_employee = st.selectbox("Select Employee", employee_ids)
            if st.button("Register Face", key="register_face_admin"):
                register_face(selected_employee)
        else:
            if st.button("Register My Face", key="register_face_employee"):
                register_face(st.session_state.current_user["employeeId"])

if __name__ == "__main__":
    main()
