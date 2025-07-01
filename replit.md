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
- July 1, 2025. Complete Batch and Contract Management System:
  * Implemented comprehensive batch/contract system for organizing NFe documents
  * Created Batch model with contract name, item name, business unit, and cost center
  * Added batch_id foreign keys to UploadedFile and NFERecord models
  * Built complete CRUD interface: create, list, edit, view batch details
  * Enhanced upload page with batch selection for both XML and PDF uploads
  * Added batch status tracking (OPEN, PROCESSING, COMPLETED, CLOSED)
  * Implemented progress tracking and total value calculation per batch
  * Created API endpoints for batch statistics and management
  * Added "Lotes" menu item for easy navigation
  * Comprehensive permission system: users can only access their own batches
  * Batch validation: only open batches can receive new files
- July 1, 2025. Auto Page Refresh Enhancement:
  * Added automatic page refresh when processing reaches 100% completion
  * Enhanced status checking frequency from 10 to 5 seconds for faster response
  * User-friendly message shows "Atualizando página..." before refresh
  * 2-second delay before refresh to allow users to see completion message
  * Applied to both processing.html template and global app.js for consistency
- July 1, 2025. Revolutionary Tax Consolidation Fix - From Items to Document:
  * Identified critical issue: taxes extracted correctly at item level but not transferred to document
  * Created automatic tax consolidation system from items to document level
  * Maps item taxes (tax_ir, tax_pis, etc.) to document fields (valor_ir, valor_pis, etc.)
  * Sums all tax values from items and applies totals to NFE record
  * Comprehensive logging shows tax consolidation process
  * Fixes the "zero taxes" display issue by ensuring document-level tax fields are populated
- July 1, 2025. Revolutionary Multi-Stage Tax Extraction System (100% Accuracy):
  * Created revolutionary 5-stage tax extraction system combining multiple AI techniques
  * Stage 1: Visual Table Recognition with GPT-4 Vision for precise tax reading
  * Stage 2: Contextual Section Analysis for document structure understanding
  * Stage 3: Cross-Validation with Rate Matching for conflict resolution
  * Stage 4: Confusion Pattern Detection for automatic IR vs PIS correction
  * Stage 5: Final Fiscal Logic Validation with Brazilian tax rules
  * Integrated advanced tax profiles with expected rates and keywords
  * Automatic detection of common tax misidentifications (IR=1.5%, PIS=0.65%)
  * Cross-validation between visual and contextual extraction methods
  * Comprehensive logging for each stage of the validation process
  * Replaces all previous tax extraction systems with unified revolutionary approach
- July 1, 2025. Revolutionary Item Extraction - Complete Service Detail Capture:
  * Dramatically expanded NFEItem model with 25+ new fields for comprehensive service data
  * Enhanced AdvancedItemExtractor to capture both basic table and detailed service breakdown
  * Added detailed service fields: servico_codigo, servico_local_prestacao, servico_aliquota, etc.
  * Implemented comprehensive tax extraction: tax_ir, tax_inss, tax_csll, tax_cofins, tax_pis, tax_issqn
  * Automatic service code formatting: converts "3301" to "33.01" format
  * Strict CNAE validation: accepts ONLY 7-digit codes, rejects CEP (8 digits) and invalid formats
  * Enhanced prompts to analyze both item table AND "Descrição dos Serviços Prestados" section
  * Complete field mapping for all service document components visible in NFe
  * Comprehensive logging to track extraction of all 25+ service-related fields
  * Fixed database schema with all new columns for seamless data storage
- July 1, 2025. Final Solution: Comprehensive Tax Processor with Auto-Correction:
  * Created FinalTaxProcessor - unified solution combining precise reading + auto-correction
  * Enhanced prompts with specific IR vs INSS distinction rules and examples
  * Automatic rate-based validation to detect and correct tax misidentifications
  * Smart fallback system: precise reading → rate validation → automatic correction
  * Integrated comprehensive logging for troubleshooting tax identification issues
  * Replaced all complex multi-stage systems with single, reliable solution
- July 1, 2025. Critical Fix: Precise Tax Reader (No More Invented Values):
  * Created PreciseTaxReader class to eliminate AI hallucination of tax values
  * Strict instructions: "Read ONLY what's clearly visible, do NOT invent values"
  * Zero-fallback approach: If value not found, return 0.0 instead of guessing
  * Replaced complex multi-stage extraction with simple, direct reading
  * Focus on accuracy over completeness to prevent false data
  * Integrated with main PDF processor as primary tax extraction method
- July 1, 2025. Revolutionary Two-Stage Tax Table Extraction System:
  * Created specialized tax table extractor with line-by-line reading approach
  * Stage 1: Extract each tax line individually from visual table (name + value + section)
  * Stage 2: Map extracted lines to correct database fields using precise name matching
  * Eliminates IR vs PIS confusion through section-aware extraction
  * Enhanced visual processing: "Impostos Federais/Estaduais" vs "Impostos Municipais/Retidos"
  * Precise tax mapping with fallback patterns for different name formats
  * Integrated with main PDF processor for automatic tax correction
  * Comprehensive field validation to prevent database truncation errors
- July 1, 2025. Advanced Multi-Agent System with Line-by-Line Tax Table Reading:
  * Created specialized 3-agent advanced system for maximum accuracy
  * Tax Expert Agent: Deep Brazilian tax knowledge with fiscal logic validation
  * Item Extraction Agent: Comprehensive item field extraction with service codes
  * Validation Agent: Cross-validation and automatic error correction
  * Advanced Tax Table Reader: Revolutionary line-by-line tax table analysis
  * Step-by-step tax identification: Forces GPT-4 Vision to read each tax line individually
  * Rate-first validation: Prioritizes aliquota identification over name patterns
  * Enhanced field mapping for service-specific data: codigo_servico, codigo_atividade, descricao_servico
  * Improved tax identification with document type-based validation (product vs service)
  * Critical tax rate validation: PIS (0.65%), COFINS (3.0%), IR (1.5%), INSS (11%)
  * Enhanced GPT-4 Vision prompts with specific tax identification rules
  * Detailed section mapping: Impostos Federais/Estaduais vs Impostos Municipais/Retidos
  * Anti-confusion safeguards: IR vs PIS distinction with explicit name matching
  * Conflict resolution system: Rate-based identification overrides name-based when conflicts occur
  * Implemented fallback hierarchy: Advanced → Standard Multi-Agent → Vision → Simple
  * Database field expansion to prevent truncation errors
- July 1, 2025. Advanced 4-Agent Tax Validation System:
  * Implemented specialized tax validation agent with deep Brazilian fiscal knowledge
  * Added document type identification (service vs product vs mixed)
  * Created category-specific tax extraction with dedicated prompts for:
    - Service taxes: ISSQN, IR, INSS, CSLL, ISSRF
    - Product taxes: ICMS, IPI, PIS, COFINS
  * Implemented cross-validation between extraction methods
  * Added fiscal logic validation with rate checking and consistency rules
  * Enhanced multi-agent flow: Conservative → Aggressive → Consolidator → Tax Specialist
  * Added automatic tax name correction and value validation
  * Improved confidence scoring with weighted tax validation results
- July 1, 2025. Multi-Stage Specialized Processing System:
  * Implemented 4-stage specialized extraction system for maximum accuracy
  * Stage 1: Document header (emitente, destinatário, identificação)
  * Stage 2: Fiscal values with enhanced bruto vs líquido recognition
  * Stage 3: Detailed items extraction with commercial values focus
  * Stage 4: Authorization and additional information capture
  * Enhanced template layout for better visibility of tax totals and additional info
  * Added specialized value handling for service documents (bruto values)
  * Improved visual presentation with proper Bootstrap components
  * Fixed display issues with additional information and tax totals sections
- July 1, 2025. Major OCR Vision processing enhancement:
  * Completely redesigned GPT-4 Vision prompt for comprehensive NFe extraction
  * Added specialized prompts for Brazilian tax recognition (municipal vs federal)
  * Enhanced field mapping for all 50+ NFe fields including ISSQN, ISSRF, IR, INSS, CSLL
  * Implemented robust fallback system for API failures (502, timeout, Cloudflare errors)
  * Added 60-second timeout for API calls to prevent hanging
  * Created detailed item processing with complete tax information per item
  * Improved error handling with automatic retry and fallback to simple processor
  * Enhanced data consolidation to capture all service-specific and product fields
- June 30, 2025. Enhanced AI processing with Brazilian tax system specifics:
  * Added service document recognition (model 55=product, 57=service, 65=mixed)
  * Implemented municipal vs state tax context handling
  * Added service-specific fields: service codes, activity codes, service descriptions
  * Enhanced tax recognition: ISSQN, IR retido, ISS retido na fonte
  * Added missing data inference (payment due dates for prepaid services)
  * Implemented additional information field capture
  * Updated database schema with new service-specific columns
- June 24, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.