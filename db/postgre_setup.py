from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class DepartmentContact(Base):
    __tablename__ = "department_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(50), nullable=False)          # e.g. "HR", "IT", "Finance"
    contact_person = Column(String(100), nullable=False)
    designation = Column(String(100), nullable=True)
    email = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=True)
    extension = Column(String(10), nullable=True)
    location = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<DepartmentContact(department={self.department}, contact_person={self.contact_person}, email={self.email})>"


def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


def get_contacts(department: str = None):
    session = SessionLocal()
    query = session.query(DepartmentContact)
    if department:
        query = query.filter(DepartmentContact.department.ilike(department))
    contacts = query.all()
    session.close()
    return [
        {
            "id": c.id,
            "department": c.department,
            "contact_person": c.contact_person,
            "designation": c.designation,
            "email": c.email,
            "phone": c.phone,
            "extension": c.extension,
            "location": c.location,
        }
        for c in contacts
    ]


def seed_sample_data():
    session = SessionLocal()
    # Only seed if table is empty
    if session.query(DepartmentContact).count() > 0:
        print("Sample data already exists. Skipping.")
        session.close()
        return

    contacts = [
        DepartmentContact(
            department="HR",
            contact_person="Priya Sharma",
            designation="HR Manager",
            email="priya.sharma@company.com",
            phone="+91-9876543210",
            extension="101",
            location="Mumbai - Floor 3",
        ),
        DepartmentContact(
            department="HR",
            contact_person="Rahul Verma",
            designation="HR Executive",
            email="rahul.verma@company.com",
            phone="+91-9876543211",
            extension="102",
            location="Mumbai - Floor 3",
        ),
        DepartmentContact(
            department="IT",
            contact_person="Ankit Patel",
            designation="IT Lead",
            email="ankit.patel@company.com",
            phone="+91-9876543212",
            extension="201",
            location="Bangalore - Floor 5",
        ),
        DepartmentContact(
            department="IT",
            contact_person="Sneha Reddy",
            designation="System Administrator",
            email="sneha.reddy@company.com",
            phone="+91-9876543213",
            extension="202",
            location="Bangalore - Floor 5",
        ),
        DepartmentContact(
            department="Finance",
            contact_person="Amit Gupta",
            designation="Finance Manager",
            email="amit.gupta@company.com",
            phone="+91-9876543214",
            extension="301",
            location="Delhi - Floor 2",
        ),
        DepartmentContact(
            department="Admin",
            contact_person="Kavita Nair",
            designation="Admin Head",
            email="kavita.nair@company.com",
            phone="+91-9876543215",
            extension="401",
            location="Mumbai - Floor 1",
        ),
        DepartmentContact(
            department="IT",
            contact_person="Deepak Kumar",
            designation="Network Engineer",
            email="deepak.kumar@company.com",
            phone="+91-9876543216",
            extension="203",
            location="Bangalore - Floor 5",
        ),
    ]

    session.add_all(contacts)
    session.commit()
    session.close()
    print(f"Inserted {len(contacts)} sample contacts.")


def test_get_contacts():
    print("\n--- All Contacts ---")
    all_contacts = get_contacts()
    for c in all_contacts:
        print(f"  [{c['department']}] {c['contact_person']} | {c['email']} | {c['phone']} | Ext: {c['extension']} | {c['location']}")

    print(f"\nTotal: {len(all_contacts)} contacts\n")

    for dept in ["HR", "IT", "Finance", "Admin"]:
        dept_contacts = get_contacts(department=dept)
        print(f"--- {dept} ({len(dept_contacts)}) ---")
        for c in dept_contacts:
            print(f"  {c['contact_person']} - {c['designation']} | {c['email']} | {c['phone']}")
        print()


if __name__ == "__main__":
    create_tables()
    # seed_sample_data()
    test_get_contacts()
