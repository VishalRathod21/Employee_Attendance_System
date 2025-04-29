# Employee Attendance System

A comprehensive employee attendance management system built with Streamlit, featuring face recognition, analytics, and automated reminders.

## Features

- **User Authentication**
  - Role-based access (Admin/Employee)
  - Secure login system
  - Session management

- **Attendance Management**
  - Face recognition-based attendance
  - Manual attendance marking
  - Real-time attendance tracking
  - Attendance history view

- **Analytics Dashboard**
  - Attendance status distribution
  - Daily attendance trends
  - Department-wise analysis
  - Custom date range selection

- **Employee Management**
  - Add new employees
  - Update employee details
  - Promote employees
  - Remove employees

- **Leave Management**
  - Apply for leave
  - Leave approval system
  - Leave history tracking
  - Leave analytics

- **Automated Features**
  - Email reminders for missing attendance
  - PDF report generation
  - Face registration system

## Prerequisites

- Python 3.8 or higher
- MongoDB database
- Webcam (for face recognition)
- SMTP server (for email notifications)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd employee-attendance-system
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following variables:
```env
MONGO_URI=your_mongodb_connection_string
DB_NAME=your_database_name
SMTP_SERVER=your_smtp_server
SMTP_PORT=your_smtp_port
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
```

## Usage

1. Start the application:
```bash
streamlit run app.py
```

2. Access the application in your web browser at `http://localhost:8501`

3. Login with your credentials:
   - Admin: Full access to all features
   - Employee: Limited access to attendance marking and leave management

## Project Structure

```
employee-attendance-system/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
└── .env                  # Environment variables (create this file)
```

## Features in Detail

### Admin Features
- View and manage all employee records
- Generate attendance reports
- Approve/reject leave applications
- Register employee faces
- Send attendance reminders
- View analytics dashboard

### Employee Features
- Mark attendance (face recognition or manual)
- View personal attendance history
- Apply for leave
- View leave status
- Register own face

## Security Features

- Password hashing
- Session management
- Role-based access control
- Secure database connections
- Environment variable configuration

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Streamlit for the web framework
- MongoDB for the database
- FaceNet for face recognition
- ReportLab for PDF generation
- Plotly for data visualization

## Support

For support, email [vr3204917@gmail.com] or open an issue in the repository.

## Future Enhancements

- Mobile application support
- Biometric integration
- Advanced analytics
- Integration with HR systems
- Multi-language support
- Dark mode
- Export to Excel
- API endpoints 
