# Domain Research Tool

## Overview

This is a domain age research application that helps users analyze domain ages for SEO and marketing purposes. The system supports both web-based and desktop interfaces for searching domains, checking their creation dates, and filtering results based on age criteria. The application integrates with Google Search API and WHOIS services to gather domain information and provides asynchronous processing for improved performance.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Web Interface**: FastAPI-based web application with HTML templates using Jinja2 templating engine
- **Desktop Interface**: PyQt6-based GUI application for desktop users
- **Responsive Design**: CSS styling with gradient backgrounds and modern UI components
- **Tab-based Navigation**: Multiple tabs for different functionality areas

### Backend Architecture
- **Core Framework**: FastAPI for the web application backend
- **Asynchronous Processing**: Uses asyncio for concurrent domain research operations
- **Task Management**: Background task system with cleanup mechanisms for long-running operations
- **Data Models**: Pydantic models for request/response validation and dataclass structures for domain data

### API Integration Layer
- **Google Search API**: Integration through RapidAPI for SERP (Search Engine Results Page) data
- **WHOIS API**: Domain registration information retrieval for age calculation
- **HTTP Client**: aiohttp for asynchronous HTTP requests with timeout handling

### Data Processing
- **Pandas Integration**: CSV file processing and data manipulation
- **Domain Age Calculation**: Date parsing and age computation using python-dateutil
- **Advanced Filtering**: Keyword-based domain criteria filtering before search execution
- **Export Functionality**: CSV export capabilities for research results

### Performance Optimizations
- **ThreadPoolExecutor**: Limited concurrent execution (max 2 workers) to prevent API rate limiting
- **Task Caching**: In-memory storage of research tasks with automatic cleanup
- **Memory Management**: Periodic cleanup of completed tasks older than 1 hour
- **Asynchronous Operations**: Non-blocking domain checks for improved throughput

### Session Management
- **Stateless Design**: Task-based processing with unique identifiers
- **Progress Tracking**: Real-time progress updates for ongoing research operations
- **Error Handling**: Comprehensive error management with status tracking

## External Dependencies

### APIs and Services
- **Google Search API** (via RapidAPI): Fetches search engine results for keyword analysis
- **WHOIS API** (via RapidAPI): Retrieves domain registration and creation date information
- **RapidAPI Platform**: Hosts both Google Search and WHOIS services

### Python Libraries
- **FastAPI**: Web framework for API development and web interface
- **PyQt6**: Desktop GUI framework for the standalone application
- **aiohttp**: Asynchronous HTTP client for API requests
- **pandas**: Data manipulation and CSV processing
- **python-dateutil**: Advanced date parsing and manipulation
- **Jinja2**: Template engine for HTML rendering
- **Pydantic**: Data validation and serialization

### Development Tools
- **asyncio**: Built-in Python library for asynchronous programming
- **concurrent.futures**: Thread-based parallelism for blocking operations
- **csv**: Standard library for CSV file operations
- **json**: JSON data processing and API response handling

### Authentication
- **API Key Management**: Environment variable-based API key storage for secure access to external services
- **RapidAPI Headers**: Custom headers for API authentication and rate limiting compliance