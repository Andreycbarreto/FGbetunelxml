# NFe XML Processor

## Overview

This Flask-based web application processes Brazilian NFe (Nota Fiscal Eletrônica) XML files using AI agents. It enables users to upload multiple XML files for sequential processing via OpenAI's GPT models and LangGraph. The system features a comprehensive user management system with role-based access control and real-time processing status updates. The project aims to streamline fiscal document processing, offering a robust solution for data extraction and validation from diverse NFe formats.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask 3.1.1 with SQLAlchemy for ORM
- **Database**: PostgreSQL 16
- **Authentication**: Hybrid (OAuth via Replit Auth and local authentication)
- **AI Processing**: OpenAI GPT-4o with LangGraph for workflow orchestration
- **XML Processing**: lxml library for parsing and validation
- **Deployment**: Gunicorn WSGI server

### Frontend Architecture
- **UI Framework**: Bootstrap 5 with dark theme
- **Icons**: Feather Icons
- **JavaScript**: Vanilla JS for real-time updates
- **Responsive Design**: Mobile-first approach, DataTables for complex data

### AI Agent Architecture
- **Multi-Agent System**: Specialized agents for NFE analysis, data extraction, and validation.
- **Workflow Orchestration**: LangGraph StateGraph for agent coordination and state management.
- **Intelligent Classification**: AI-powered classification (GPT-4o) for document operation types (e.g., "Serviços e Produtos" vs. "CT-e (Transporte)").
- **Tax Extraction**: Revolutionary multi-stage tax extraction with auto-correction and rate-based validation.
- **Item Extraction**: Comprehensive capture of service details and tax information per item.

### Core System Features
- **User Management**: Roles (ADMIN, USER, VIEWER) and secure authentication.
- **File Management**: Secure upload, queue management, and status tracking.
- **Data Storage**: NFe data and extracted items stored in PostgreSQL with AI confidence scores.
- **Fluig Integration**: Automated workflow launch for NFe documents, including process creation, document attachment, and real-time solicitation number capture. Includes intelligent duplicate detection and robust error handling.
- **Company and Branch Management**: CRUD operations for managing companies and branches (filiais) with CNPJ-based lookup and batch import from Excel.
- **PDF Download**: Secure download of original uploaded PDF files.
- **Universal Document Processing**: Adaptive processing for various NFe PDF formats (DANFE, NFS-e, government formats) using intelligent layout detection and specialized GPT-4 Vision prompts. Includes enhanced date extraction and Brazilian format compatibility.
- **Batch and Contract Management**: Organization of NFe documents into batches with status tracking and progress calculation.

## External Dependencies

### Required Services
- **OpenAI API**: GPT-4o model for AI processing.
- **PostgreSQL Database**: Primary data storage.
- **Replit OAuth**: Optional OAuth authentication service.
- **Fluig API**: For workflow integration and document management.

### Python Dependencies
- **Core**: Flask, SQLAlchemy, Gunicorn
- **AI/ML**: OpenAI, LangGraph, LangChain-core
- **XML Processing**: lxml
- **Authentication**: Flask-Login, Flask-Dance, PyJWT
- **Database**: psycopg2-binary
- **Utilities**: email-validator, werkzeug