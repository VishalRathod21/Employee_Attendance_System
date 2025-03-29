import streamlit as st
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, date, timedelta
import pandas as pd
import certifi
import plotly.express as px

# --- Configuration ---
load_dotenv()

# --- Database Setup ---
@st.cache_resource
def get_db_client():
    try:
        client = MongoClient(
            os.getenv("MONGO_URI"),
            tlsCAFile=certifi.where()
        )
        client.admin.command('ping')  # Test connection
        return client
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        st.stop()

class AttendanceDB:
    def __init__(self, client, db_name):
        self.db = client[db_name]
    
    # Employee operations
    def add_employee(self, employee_data):
        return self.db.employees.insert_one(employee_data)
    
    def get_employees(self, query=None):
        query = query or {}
        return list(self.db.employees.find(query, {'_id': 0}))
    
    def update_employee(self, emp_id, update_data):
        return self.db.employees.update_one(
            {"employeeId": emp_id},
            {"$set": update_data}
        )
    
    def delete_employee(self, emp_id):
        return self.db.employees.delete_one({"employeeId": emp_id})
    
    # Attendance operations
    def mark_attendance(self, attendance_data):
        return self.db.attendance.insert_one(attendance_data)
    
    def get_attendance(self, query=None):
        query = query or {}
        return list(self.db.attendance.find(query, {'_id': 0}))
    
    def get_attendance_by_date(self, date_str):
        return self.db.attendance.find_one({"date": date_str})
    
    def delete_attendance(self, date_str):
        return self.db.attendance.delete_one({"date": date_str})

# --- Initialize App ---
st.set_page_config(
    page_title="Employee Attendance System",
    layout="wide",
    page_icon="👨‍💼"
)

# --- Initialize Database ---
try:
    client = get_db_client()
    db = AttendanceDB(client, os.getenv("DB_NAME"))
except Exception as e:
    st.error(f"Failed to initialize database: {str(e)}")
    st.stop()

# --- Helper Functions ---
def display_employee_table(employees):
    if not employees:
        st.info("No employees found")
        return
    
    df = pd.DataFrame([{
        "ID": emp["employeeId"],
        "Name": emp["empName"],
        "Department": emp["department"],
        "Position": emp["position"],
        "Email": emp["email"],
        "Mobile": emp["mobile"],
        "Join Date": emp.get("joinDate", "N/A")
    } for emp in employees])
    
    st.dataframe(df, use_container_width=True)

def process_attendance_data(attendance_records, filter_emp_id=None):
    all_employees = {e["employeeId"]: e for e in db.get_employees()}
    data = []
    for record in attendance_records:
        for emp in record["employees"]:
            if filter_emp_id and emp["employeeId"] != filter_emp_id:
                continue
            employee_info = all_employees.get(emp["employeeId"], {})    
            data.append({
                "Date": record["date"],
                "ID": emp["employeeId"],
                "Name": employee_info.get("empName", "N/A"),  # Added Name
                "Status": emp["status"],
                "Check-in": emp.get("checkIn", "N/A"),
                "Check-out": emp.get("checkOut", "N/A"),
                "Department": employee_info.get("department", "N/A")
            })
    return pd.DataFrame(data) if data else None

# --- Main App ---
st.title("👨‍💼 Employee Attendance System")
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "➕ Add Employee", 
    "📝 Mark Attendance", 
    "📊 View Records", 
    "📈 Analytics",
    "⚙️ Manage Employees"
])

# --- Tab 1: Add Employee ---
with tab1:
    st.header("Add New Employee")
    
    with st.form("add_employee_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        emp_id = col1.text_input("Employee ID*", help="Unique identifier for the employee")
        full_name = col2.text_input("Full Name*")
        email = col1.text_input("Email*")
        mobile = col2.text_input("Mobile Number*")
        department = st.selectbox(
            "Department*",
            ["HR", "IT", "Finance", "Operations", "Marketing", "Sales"]
        )
        position = st.selectbox(
            "Position*",
            ["Intern", "Associate", "Senior", "Lead", "Manager", "Director"]
        )
        
        if st.form_submit_button("Add Employee"):
            if not all([emp_id, full_name, email, department, position]):
                st.error("Please fill all required fields!")
            elif any(emp["employeeId"] == emp_id for emp in db.get_employees()):
                st.error(f"Employee ID {emp_id} already exists!")
            else:
                try:
                    db.add_employee({
                        "employeeId": emp_id,
                        "empName": full_name,
                        "email": email,
                        "mobile": mobile,
                        "department": department,
                        "position": position,
                        "joinDate": datetime.now().strftime("%Y-%m-%d")
                    })
                    st.success(f"Employee {full_name} added successfully!")
                except Exception as e:
                    st.error(f"Error adding employee: {str(e)}")

# --- Tab 2: Mark Attendance ---
with tab2:
    st.header("Mark Attendance")
    
    selected_date = st.date_input("Select Date", date.today())
    employees = db.get_employees()
    
    if not employees:
        st.warning("No employees found. Please add employees first.")
    else:
        existing_attendance = db.get_attendance_by_date(selected_date.strftime("%Y-%m-%d"))
        
        if existing_attendance:
            st.warning(f"Attendance already marked for {selected_date}")
            
            if st.button("Delete and Re-mark Attendance"):
                db.delete_attendance(selected_date.strftime("%Y-%m-%d"))
                st.rerun 加
            attendance_df = process_attendance_data([existing_attendance])
            st.dataframe(attendance_df, use_container_width=True)
        else:
            with st.form("attendance_form"):
                st.subheader("Mark Attendance Status")
                
                attendance_records = []
                for emp in employees:
                    cols = st.columns([1, 2, 2, 2])
                    cols[0].write(emp["employeeId"])
                    cols[1].write(emp["empName"])
                    cols[2].write(emp["department"])
                    
                    status = cols[3].selectbox(
                        "Status",
                        ["Present", "Absent", "Leave", "Half-Day", "Late"],
                        key=f"status_{emp['employeeId']}_{selected_date}",
                        index=0
                    )
                    
                    attendance_records.append({
                        "employeeId": emp["employeeId"],
                        "status": status
                    })
                
                if st.form_submit_button("Submit Attendance"):
                    try:
                        db.mark_attendance({
                            "date": selected_date.strftime("%Y-%m-%d"),
                            "markedAt": datetime.now(),
                            "employees": attendance_records
                        })
                        st.success("Attendance marked successfully!")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

# --- Tab 3: View Records ---
with tab3:
    st.header("Attendance Records")
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", date.today() - timedelta(days=30))
    end_date = col2.date_input("End Date", date.today())
    
    employees = db.get_employees()
    selected_employee = st.selectbox(
        "Filter by Employee (Optional)",
        [None] + [emp["employeeId"] for emp in employees]
    )
    
    if st.button("Load Records"):
        query = {
            "date": {
                "$gte": start_date.strftime("%Y-%m-%d"),
                "$lte": end_date.strftime("%Y-%m-%d")
            }
        }
        
        records = db.get_attendance(query)
        attendance_df = process_attendance_data(records, selected_employee)
        
        if attendance_df is not None:
            st.dataframe(attendance_df, use_container_width=True)
            
            # Download options
            csv = attendance_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download as CSV",
                csv,
                f"attendance_{start_date}_to_{end_date}.csv",
                "text/csv"
            )
        else:
            st.info("No attendance records found for the selected period")

# --- Tab 4: Analytics ---
with tab4:
    st.header("Attendance Analytics")
    
    analysis_type = st.radio(
        "Select Analysis Type",
        ["Monthly Summary", "Employee Statistics", "Department Comparison"]
    )
    
    if analysis_type == "Monthly Summary":
        selected_month_date = st.date_input(
            "Select Month",
            datetime.now().replace(day=1),
        )
        selected_month = selected_month_date.strftime("%Y-%m")
        
        records = db.get_attendance({
            "date": {"$regex": f"^{selected_month}"}
        })
        
        if records:
            df = process_attendance_data(records)
            if df is None:
                st.warning(f"No attendance data available for {selected_month}")
            else:
                summary = df.groupby(["ID", "Name", "Department"])["Status"].value_counts().unstack().fillna(0)
                summary["Total"] = summary.sum(axis=1)
                summary["Attendance %"] = (summary.get("Present", 0) / summary["Total"] * 100)
                
                st.dataframe(summary.style.format("{:.1f}", subset=["Attendance %"]))
                
                fig = px.bar(
                    summary.reset_index(),
                    x="Name",
                    y=["Present", "Absent", "Leave"],
                    title=f"Attendance Summary for {selected_month}",
                    labels={"value": "Days", "variable": "Status"}
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No attendance records found for {selected_month}")
    
    elif analysis_type == "Employee Statistics":
        selected_employee = st.selectbox(
            "Select Employee",
            [emp["employeeId"] for emp in db.get_employees()]
        )
        
        records = db.get_attendance({
            "employees.employeeId": selected_employee
        })
        
        if records:
            df = process_attendance_data(records, selected_employee)
            if df is None:
                st.warning(f"No attendance data available for employee {selected_employee}")
            else:
                status_counts = df["Status"].value_counts()
                present_percentage = status_counts.get("Present", 0) / len(df) * 100
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Days Recorded", len(df))
                col2.metric("Present Days", status_counts.get("Present", 0))
                col3.metric("Attendance Rate", f"{present_percentage:.1f}%")
                
                fig = px.line(
                    df,
                    x="Date",
                    y="Status",
                    title=f"Attendance History for Employee {selected_employee}",
                    category_orders={"Status": ["Present", "Late", "Half-Day", "Leave", "Absent"]}
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No attendance records found for employee {selected_employee}")
    
    elif analysis_type == "Department Comparison":
        time_period = st.selectbox(
            "Time Period",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom Range"]
        )
        
        if time_period == "Custom Range":
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Start Date", date.today() - timedelta(days=30))
            end_date = col2.date_input("End Date", date.today())
        else:
            days = int(time_period.split()[1])
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
        
        records = db.get_attendance({
            "date": {
                "$gte": start_date.strftime("%Y-%m-%d"),
                "$lte": end_date.strftime("%Y-%m-%d")
            }
        })
        
        if records:
            df = process_attendance_data(records)
            if df is None:
                st.warning(f"No attendance data available for the selected period")
            else:
                dept_stats = df.groupby("Department")["Status"].value_counts().unstack().fillna(0)
                dept_stats["Total"] = dept_stats.sum(axis=1)
                
                for status in ["Present", "Absent", "Leave"]:
                    if status in dept_stats:
                        dept_stats[f"{status} %"] = dept_stats[status] / dept_stats["Total"] * 100
                
                st.dataframe(dept_stats.style.format("{:.1f}%", subset=[col for col in dept_stats if "%" in col]))
                
                fig = px.pie(
                    dept_stats.reset_index(),
                    names="Department",
                    values="Present",
                    title="Present Employees by Department"
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No attendance records found for the selected period")

# --- Tab 5: Manage Employees ---
with tab5:
    st.header("Employee Management")
    
    employees = db.get_employees()
    if not employees:
        st.info("No employees found in the database")
        st.stop()
    
    st.subheader("All Employees")
    display_employee_table(employees)
    
    st.subheader("Employee Actions")
    action = st.radio(
        "Select Action",
        ["Update Details", "Change Department", "Change Position", "Terminate Employment"]
    )
    
    selected_employee = st.selectbox(
        "Select Employee",
        [emp["employeeId"] for emp in employees],
        key="employee_select"
    )
    
    employee_data = next(emp for emp in employees if emp["employeeId"] == selected_employee)
    
    if action == "Update Details":
        with st.form("update_employee_form"):
            new_email = st.text_input("Email", employee_data["email"])
            new_mobile = st.text_input("Mobile", employee_data["mobile"])
            
            if st.form_submit_button("Update Details"):
                update_data = {
                    "email": new_email,
                    "mobile": new_mobile
                }
                result = db.update_employee(selected_employee, update_data)
                if result.modified_count > 0:
                    st.success("Employee details updated successfully!")
                else:
                    st.warning("No changes were made")
    
    elif action == "Change Department":
        with st.form("change_dept_form"):
            new_department = st.selectbox(
                "New Department",
                ["HR", "IT", "Finance", "Operations", "Marketing", "Sales"],
                index=["HR", "IT", "Finance", "Operations", "Marketing", "Sales"].index(
                    employee_data["department"]
                )
            )
            
            if st.form_submit_button("Change Department"):
                result = db.update_employee(selected_employee, {"department": new_department})
                if result.modified_count > 0:
                    st.success(f"Department changed to {new_department}")
                else:
                    st.warning("No changes were made")
    
    elif action == "Change Position":
        with st.form("change_position_form"):
            new_position = st.selectbox(
                "New Position",
                ["Intern", "Associate", "Senior", "Lead", "Manager", "Director"],
                index=["Intern", "Associate", "Senior", "Lead", "Manager", "Director"].index(
                    employee_data["position"]
                )
            )
            
            if st.form_submit_button("Change Position"):
                result = db.update_employee(selected_employee, {"position": new_position})
                if result.modified_count > 0:
                    st.success(f"Position changed to {new_position}")
                else:
                    st.warning("No changes were made")
    
    elif action == "Terminate Employment":
        st.warning("This action cannot be undone!")
        confirm = st.checkbox("I understand this will permanently remove the employee record")
        
        if confirm and st.button("Terminate Employment"):
            has_records = len(db.get_attendance({
                "employees.employeeId": selected_employee
            })) > 0
            
            if has_records:
                st.warning("This employee has attendance records. Their attendance data will remain but will no longer be associated with their employee ID.")
            
            result = db.delete_employee(selected_employee)
            if result.deleted_count > 0:
                st.success(f"Employee {selected_employee} terminated successfully")
                st.rerun()
            else:
                st.error("Failed to terminate employee")

# --- Footer ---
st.markdown("---")
st.caption("Employee Attendance System v1.0 | © 2023")
