import streamlit as st
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, date
import pandas as pd

# Load environment variables
load_dotenv()

# Initialize MongoDB client
mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("DB_NAME")

client = MongoClient(mongo_uri)
db = client[db_name]
employees_col = db["employees"]
attendance_col = db["attendance"]

# Streamlit App Configuration
st.set_page_config(page_title="Employee Attendance System", layout="wide")
st.title("📋 Employee Attendance System")

# Initialize session states
if 'add_form_key' not in st.session_state:
    st.session_state.add_form_key = 0

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Add Employee", 
    "Mark Attendance", 
    "View Attendance", 
    "Reports",
    "Employee Management"
])

# Tab 1: Add Employee
with tab1:
    st.header("👨‍💼 Add New Employee")
    with st.form(key=f"add_form_{st.session_state.add_form_key}", clear_on_submit=True):
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

# Tab 2: Mark Attendance
with tab2:
    st.header("🖊️ Mark Attendance")
    
    # Date selection
    attendance_date = st.date_input("Select Date", date.today())
    
    # Get all employees
    all_employees = list(employees_col.find())
    
    if not all_employees:
        st.warning("No employees found in the database. Please add employees first.")
    else:
        # Check if attendance already marked for today
        existing_attendance = attendance_col.find_one({
            "date": attendance_date.strftime("%Y-%m-%d")
        })
        
        if existing_attendance:
            st.warning(f"Attendance already marked for {attendance_date.strftime('%Y-%m-%d')}")
            st.write("Existing attendance records:")
            
            # Display existing attendance
            attendance_records = list(attendance_col.find({
                "date": attendance_date.strftime("%Y-%m-%d")
            }))
            
            attendance_data = []
            for record in attendance_records:
                for emp_record in record["employees"]:
                    emp = employees_col.find_one({"employeeId": emp_record["employeeId"]})
                    attendance_data.append({
                        "ID": emp_record["employeeId"],
                        "Name": emp["empName"],
                        "Department": emp["department"],
                        "Status": emp_record["status"],
                        "Check-in": emp_record.get("checkIn", "N/A"),
                        "Check-out": emp_record.get("checkOut", "N/A")
                    })
            
            st.dataframe(pd.DataFrame(attendance_data), use_container_width=True)
        else:
            # Create attendance form
            with st.form(key="attendance_form"):
                attendance_records = []
                
                st.subheader("Mark Attendance Status")
                cols = st.columns([2, 2, 2, 1])
                cols[0].write("**Employee ID**")
                cols[1].write("**Name**")
                cols[2].write("**Department**")
                cols[3].write("**Status**")
                
                for emp in all_employees:
                    cols = st.columns([2, 2, 2, 1])
                    cols[0].write(emp["employeeId"])
                    cols[1].write(emp["empName"])
                    cols[2].write(emp["department"])
                    
                    # Default to "Present" for each employee
                    status = cols[3].selectbox(
                        f"Status_{emp['employeeId']}",
                        ["Present", "Absent", "Leave", "Late"],
                        key=f"status_{emp['employeeId']}",
                        label_visibility="collapsed"
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
                    
                    try:
                        attendance_col.insert_one(attendance_doc)
                        st.success("Attendance marked successfully!")
                    except Exception as e:
                        st.error(f"Error marking attendance: {e}")

# Tab 3: View Attendance
with tab3:
    st.header("📅 View Attendance Records")
    
    # Date range selection
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", date.today())
    end_date = col2.date_input("End Date", date.today())
    
    # Employee filter
    all_employees = list(employees_col.find())
    employee_ids = [emp["employeeId"] for emp in all_employees]
    selected_employee = st.selectbox("Filter by Employee (Optional)", [None] + employee_ids)
    
    if st.button("Load Attendance"):
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
            
            # Download button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download as CSV",
                csv,
                f"attendance_{start_date}_to_{end_date}.csv",
                "text/csv"
            )

# Tab 4: Reports
with tab4:
    st.header("📈 Attendance Reports")
    
    # Monthly attendance summary
    st.subheader("Monthly Summary")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_to_analyze = st.text_input("Enter month to analyze (YYYY-MM)", current_month)
    
    if st.button("Generate Report"):
        try:
            # Get all attendance records for the month
            start_date = f"{month_to_analyze}-01"
            end_date = f"{month_to_analyze}-31"
            
            attendance_records = list(attendance_col.find({
                "date": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }))
            
            if not attendance_records:
                st.warning(f"No attendance records found for {month_to_analyze}")
            else:
                # Process data for report
                report_data = []
                employees = list(employees_col.find())
                
                for emp in employees:
                    emp_id = emp["employeeId"]
                    emp_name = emp["empName"]
                    department = emp["department"]
                    
                    # Count different statuses
                    present = 0
                    absent = 0
                    leave = 0
                    late = 0
                    
                    for record in attendance_records:
                        for emp_record in record["employees"]:
                            if emp_record["employeeId"] == emp_id:
                                status = emp_record["status"]
                                if status == "Present":
                                    present += 1
                                elif status == "Absent":
                                    absent += 1
                                elif status == "Leave":
                                    leave += 1
                                elif status == "Late":
                                    late += 1
                    
                    total_days = present + absent + leave + late
                    attendance_percentage = (present + late) / total_days * 100 if total_days > 0 else 0
                    
                    report_data.append({
                        "ID": emp_id,
                        "Name": emp_name,
                        "Department": department,
                        "Present": present,
                        "Absent": absent,
                        "Leave": leave,
                        "Late": late,
                        "Total Days": total_days,
                        "Attendance %": f"{attendance_percentage:.1f}%"
                    })
                
                # Display report
                report_df = pd.DataFrame(report_data)
                st.dataframe(report_df, use_container_width=True)
                
                # Visualization
                st.subheader("Department-wise Summary")
                dept_summary = report_df.groupby("Department").agg({
                    "Present": "sum",
                    "Absent": "sum",
                    "Leave": "sum",
                    "Late": "sum"
                }).reset_index()
                
                st.bar_chart(dept_summary.set_index("Department"))
                
        except Exception as e:
            st.error(f"Error generating report: {e}")

# Tab 5: Employee Management
with tab5:
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
        with st.form(key="promote_form"):
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
        with st.form(key="update_form"):
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
        with st.form(key="remove_form"):
            emp_id = st.selectbox("Select Employee to Remove", employee_ids)
            
            if st.form_submit_button("Remove"):
                # Check if employee has attendance records
                has_attendance = attendance_col.count_documents({
                    "employees.employeeId": emp_id
                }) > 0
                
                if has_attendance:
                    st.warning("This employee has attendance records. Deleting will remove all associated data.")
                    confirm = st.checkbox("I understand and want to proceed")
                    if not confirm:
                        st.stop()
                
                # Delete employee and their attendance records
                employees_col.delete_one({"employeeId": emp_id})
                attendance_col.update_many(
                    {},
                    {"$pull": {"employees": {"employeeId": emp_id}}}
                )
                st.success(f"Employee {emp_id} removed successfully!")