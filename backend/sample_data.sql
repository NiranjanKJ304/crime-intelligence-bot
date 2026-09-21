-- ==============================================================================
-- Karnataka Police Crime Intelligence Database — Schema & Sample Seed Data
-- ==============================================================================

-- 1. Create Public Schema Tables
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

-- District
CREATE TABLE public."District" (
    "District_ID" INT PRIMARY KEY,
    "District_Name" VARCHAR(100) NOT NULL
);

-- Unit (Police Station)
CREATE TABLE public."Unit" (
    "Unit_ID" INT PRIMARY KEY,
    "District_ID" INT REFERENCES public."District"("District_ID"),
    "Unit_Name" VARCHAR(100) NOT NULL
);

-- Court
CREATE TABLE public."Court" (
    "Court_ID" INT PRIMARY KEY,
    "Court_Name" VARCHAR(150) NOT NULL
);

-- Employee (Police Officers)
CREATE TABLE public."Employee" (
    "Employee_ID" INT PRIMARY KEY,
    "Unit_ID" INT REFERENCES public."Unit"("Unit_ID"),
    "First_Name" VARCHAR(100) NOT NULL,
    "KGID" VARCHAR(50),
    "Designation" VARCHAR(50),
    "Rank" VARCHAR(50)
);

-- CaseMaster (FIRs / Cases)
CREATE TABLE public."CaseMaster" (
    "Case_ID" INT PRIMARY KEY,
    "FIR_No" VARCHAR(50) NOT NULL,
    "Crime_No" VARCHAR(50) NOT NULL,
    "Unit_ID" INT REFERENCES public."Unit"("Unit_ID"),
    "District_ID" INT REFERENCES public."District"("District_ID"),
    "Court_ID" INT REFERENCES public."Court"("Court_ID"),
    "IO_ID" INT REFERENCES public."Employee"("Employee_ID"),
    "Crime_Date" TIMESTAMP NOT NULL,
    "Status" VARCHAR(50) NOT NULL,
    "Latitude" DOUBLE PRECISION,
    "Longitude" DOUBLE PRECISION,
    "Narrative" TEXT
);

-- ComplainantDetails
CREATE TABLE public."ComplainantDetails" (
    "Complainant_ID" INT PRIMARY KEY,
    "Case_ID" INT REFERENCES public."CaseMaster"("Case_ID"),
    "Name" VARCHAR(100) NOT NULL,
    "Address" VARCHAR(250),
    "Phone" VARCHAR(30)
);

-- Victim
CREATE TABLE public."Victim" (
    "Victim_ID" INT PRIMARY KEY,
    "Case_ID" INT REFERENCES public."CaseMaster"("Case_ID"),
    "Name" VARCHAR(100) NOT NULL,
    "Age" INT,
    "Gender" VARCHAR(10)
);

-- Accused
CREATE TABLE public."Accused" (
    "Accused_ID" INT PRIMARY KEY,
    "Case_ID" INT REFERENCES public."CaseMaster"("Case_ID"),
    "Name" VARCHAR(100) NOT NULL,
    "Age" INT,
    "Gender" VARCHAR(10)
);

-- ActSectionAssociation
CREATE TABLE public."ActSectionAssociation" (
    "ID" INT PRIMARY KEY,
    "Case_ID" INT REFERENCES public."CaseMaster"("Case_ID"),
    "Act_ID" INT NOT NULL,
    "Section_ID" INT NOT NULL,
    "Act_Name" VARCHAR(100),
    "Section_Name" VARCHAR(100)
);

-- ChargesheetDetails
CREATE TABLE public."ChargesheetDetails" (
    "CS_ID" INT PRIMARY KEY,
    "Case_ID" INT REFERENCES public."CaseMaster"("Case_ID"),
    "CS_No" VARCHAR(50),
    "CS_Date" TIMESTAMP,
    "Status" VARCHAR(50)
);

-- ArrestSurrender
CREATE TABLE public."ArrestSurrender" (
    "Arrest_ID" INT PRIMARY KEY,
    "Case_ID" INT REFERENCES public."CaseMaster"("Case_ID"),
    "Accused_ID" INT REFERENCES public."Accused"("Accused_ID"),
    "Arrest_Date" TIMESTAMP,
    "Arrest_By" INT REFERENCES public."Employee"("Employee_ID")
);


-- ==============================================================================
-- 2. Insert Sample Seed Data
-- ==============================================================================

-- Districts
INSERT INTO public."District" ("District_ID", "District_Name") VALUES
(1, 'Bengaluru City'),
(2, 'Mysuru City'),
(3, 'Mangaluru City');

-- Police Stations (Units)
INSERT INTO public."Unit" ("Unit_ID", "District_ID", "Unit_Name") VALUES
(101, 1, 'Koramangala Police Station'),
(102, 1, 'Indiranagar Police Station'),
(103, 2, 'Devaraja Police Station');

-- Courts
INSERT INTO public."Court" ("Court_ID", "Court_Name") VALUES
(501, 'Chief Metropolitan Magistrate Court Bengaluru'),
(502, 'JMFC 1st Court Mysuru');

-- Officers (Employees)
INSERT INTO public."Employee" ("Employee_ID", "Unit_ID", "First_Name", "KGID", "Designation", "Rank") VALUES
(1001, 101, 'Ramesh Kumar', 'KG10982', 'Inspector of Police', 'Inspector'),
(1002, 101, 'Sunil Gowda', 'KG10442', 'Sub-Inspector', 'PSI'),
(1003, 102, 'Priya Sharma', 'KG11200', 'Inspector of Police', 'Inspector');

-- Cases
INSERT INTO public."CaseMaster" ("Case_ID", "FIR_No", "Crime_No", "Unit_ID", "District_ID", "Court_ID", "IO_ID", "Crime_Date", "Status", "Latitude", "Longitude", "Narrative") VALUES
(1, 'FIR/2026/001', 'CR-001/2026', 101, 1, 501, 1001, '2026-03-10 22:30:00', 'Under Investigation', 12.9352, 77.6245, 'Night burglary reported at electronic appliance store in Koramangala 4th Block. Multiple laptops and cash stolen.'),
(2, 'FIR/2026/002', 'CR-002/2026', 102, 1, 501, 1003, '2026-03-12 14:15:00', 'Chargesheeted', 12.9784, 77.6408, 'Armed robbery and extortion incident on 100 Feet Road Indiranagar. Suspect apprehended with weapon and illicit vehicle.'),
(3, 'FIR/2026/003', 'CR-003/2026', 101, 1, 501, 1002, '2026-03-15 01:45:00', 'Pending Trial', 12.9279, 77.6271, 'Two-wheeler chain snatching incident near Sony World Signal. Victim was walking home late at night.');

-- Complainants
INSERT INTO public."ComplainantDetails" ("Complainant_ID", "Case_ID", "Name", "Address", "Phone") VALUES
(201, 1, 'Anand Verma', '45, 80ft Road, Koramangala, Bengaluru', '9845012345'),
(202, 2, 'Vikram Hegde', '12, 100ft Road, Indiranagar, Bengaluru', '9845054321'),
(203, 3, 'Deepa Rao', '89, 5th Main, Koramangala, Bengaluru', '9845098765');

-- Victims
INSERT INTO public."Victim" ("Victim_ID", "Case_ID", "Name", "Age", "Gender") VALUES
(301, 1, 'Anand Verma', 42, 'Male'),
(302, 2, 'Vikram Hegde', 35, 'Male'),
(303, 3, 'Deepa Rao', 28, 'Female');

-- Accused
INSERT INTO public."Accused" ("Accused_ID", "Case_ID", "Name", "Age", "Gender") VALUES
(401, 1, 'Syed Imran', 29, 'Male'),
(402, 1, 'Kiran Kumar', 26, 'Male'),
(403, 2, 'Syed Imran', 29, 'Male'),
(404, 3, 'Manjunath B', 24, 'Male');

-- Acts & Sections
INSERT INTO public."ActSectionAssociation" ("ID", "Case_ID", "Act_ID", "Section_ID", "Act_Name", "Section_Name") VALUES
(601, 1, 1, 457, 'Indian Penal Code', 'Section 457 (Lurking house-trespass/burglary by night)'),
(602, 1, 1, 380, 'Indian Penal Code', 'Section 380 (Theft in dwelling house)'),
(603, 2, 1, 392, 'Indian Penal Code', 'Section 392 (Robbery)'),
(604, 2, 1, 397, 'Indian Penal Code', 'Section 397 (Robbery with attempt to cause death/grievous hurt)'),
(605, 3, 1, 379, 'Indian Penal Code', 'Section 379 (Snatching / Theft)');

-- Chargesheets
INSERT INTO public."ChargesheetDetails" ("CS_ID", "Case_ID", "CS_No", "CS_Date", "Status") VALUES
(701, 2, 'CS-102/2026', '2026-03-25 10:00:00', 'Submitted to Court');

-- Arrests
INSERT INTO public."ArrestSurrender" ("Arrest_ID", "Case_ID", "Accused_ID", "Arrest_Date", "Arrest_By") VALUES
(801, 1, 401, '2026-03-11 06:00:00', 1001),
(802, 2, 403, '2026-03-12 18:00:00', 1003);
