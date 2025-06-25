# NFe XML Processor

## Overview

This is a Flask-based web application designed to process Brazilian NFe (Nota Fiscal Eletrônica) XML files using AI agents. The system allows users to upload multiple XML files, which are then processed sequentially using OpenAI's GPT models and LangGraph workflow orchestration. The application provides a complete user management system with role-based access control and real-time processing status updates.

## System Architecture

### Backend Architecture
- **Framework**: Flask 3.1.1 with SQLAlchemy for ORM
- **Database**: PostgreSQL 16 with SQLAlchemy 2.0.41
- **Authentication**: Hybrid system supporting both OAuth (Replit Auth) and local authentication
- **AI Processing**: OpenAI GPT-4o with LangGraph workflow orchestration
- **XML Processing**: lxml library for XML parsing and validation
- **Deployment**: Gunicorn WSGI server with autoscale deployment target

### Frontend Architecture
- **UI Framework**: Bootstrap 5 with dark theme support
- **Icons**: Feather Icons
- **JavaScript**: Vanilla JS with real-time updates
- **Responsive Design**: Mobile-first approach with DataTables for complex data display

### AI Agent Architecture
- **Multi-Agent System**: Specialized agents for different processing stages
  - NFE Analysis Agent: Analyzes XML structure and content
  - Data Extraction Agent: Extracts structured data from XML
  - Validation Agent: Validates extracted data quality
- **Workflow Orchestration**: LangGraph StateGraph for agent coordination
- **State Management**: Shared state between agents with error tracking

## Key Components

### Models
- **User**: Complete user management with roles (ADMIN, USER, VIEWER)
- **UploadedFile**: File upload tracking with metadata
- **NFERecord**: Main NFe data storage with AI confidence scores
- **NFEItem**: Individual line items within NFe documents
- **OAuth**: OAuth token storage for external authentication

### Core Services
- **XML Processor**: Handles NFe XML parsing and initial data extraction
- **AI Agents**: Multi-agent system for intelligent data processing
- **Authentication System**: Hybrid OAuth + local auth with role-based access
- **File Upload System**: Secure file handling with validation

### Routes and Controllers
- **Authentication Routes**: Login, logout, OAuth callbacks
- **File Management**: Upload, processing queue, status tracking
- **Data Views**: Dashboard, detailed record views, admin panels
- **API Endpoints**: Real-time status updates, file processing

## Data Flow

1. **File Upload**: Users upload multiple XML files through drag-and-drop interface
2. **Queue Management**: Files are queued for sequential processing
3. **XML Parsing**: Initial parsing extracts basic document structure
4. **AI Processing**: Multi-agent workflow processes XML content:
   - Analysis agent identifies key sections
   - Extraction agent pulls structured data
   - Validation agent ensures data quality
5. **Data Storage**: Processed data stored in PostgreSQL with confidence scores
6. **User Interface**: Real-time updates show processing status and results

## External Dependencies

### Required Services
- **OpenAI API**: GPT-4o model for AI processing (requires OPENAI_API_KEY)
- **PostgreSQL Database**: Primary data storage (configured via DATABASE_URL)
- **Replit OAuth**: Optional OAuth authentication service

### Python Dependencies
- **Core**: Flask, SQLAlchemy, Gunicorn
- **AI/ML**: OpenAI, LangGraph, LangChain-core
- **XML Processing**: lxml
- **Authentication**: Flask-Login, Flask-Dance, PyJWT
- **Database**: psycopg2-binary
- **Utilities**: email-validator, werkzeug

## Deployment Strategy

### Environment Configuration
- **Development**: Local Flask development server
- **Production**: Gunicorn with autoscale deployment on Replit
- **Database**: PostgreSQL with connection pooling and auto-reconnection
- **File Storage**: Local filesystem with configurable upload directory

### Security Measures
- **Authentication**: Hybrid OAuth + local password authentication
- **File Validation**: XML file type validation and size limits (50MB)
- **CSRF Protection**: Flask session-based protection
- **Role-based Access**: Admin, User, and Viewer permission levels

### Performance Optimizations
- **Database**: Connection pooling with 300s recycle time
- **File Processing**: Sequential processing to manage resource usage
- **Frontend**: Responsive design with lazy loading for large datasets
- **Caching**: SQLAlchemy query optimization with eager loading

## Changelog
- June 24, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.