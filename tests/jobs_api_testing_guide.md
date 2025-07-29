# Jobs API Testing Guide

This guide provides examples for testing the Jobs API endpoints using Postman.

## Base URL
```
http://localhost:8000/jobs
```

## 1. Get Paginated Jobs (Enhanced)

**Endpoint:** `GET /api/jobs/paginated`

**Description:** Get paginated jobs with optional filters, search query, and sorting

### Basic Request
```
GET http://localhost:8000/jobs/paginated?limit=10
```

### With Search Query
```
GET http://localhost:8000/jobs/paginated?limit=10&q=python
```

### With Multiple Locations
```
GET http://localhost:8000/jobs/paginated?limit=10&location=San Francisco,New York,Remote
```

### With Multiple Specializations
```
GET http://localhost:8000/jobs/paginated?limit=10&specialization=backend,frontend,fullstack
```

### With Sorting
```
GET http://localhost:8000/jobs/paginated?limit=10&sort_by=salary_max_range&sort_order=desc
```

### With Filters
```
GET http://localhost:8000/jobs/paginated?limit=10&location=San Francisco,New York&job_type=fulltime&experience_level=senior&salary_min=100000&salary_max=200000&provides_sponsorship=true
```

### Combined Search, Sort, and Filter
```
GET http://localhost:8000/jobs/paginated?limit=10&q=react&sort_by=salary_max_range&sort_order=desc&location=San Francisco,Remote&specialization=frontend,fullstack
```

### Query Parameters
- `limit` (int, 1-100): Number of jobs to return (default: 9)
- `last_job_id` (string, optional): Last job ID for pagination
- `q` (string, optional): Search query for title, company, description, or skills
- `sort_by` (string): Sort by field (id, created_at, salary_min_range, salary_max_range, score) (default: id)
- `sort_order` (string): Sort order (asc, desc) (default: desc)
- `location` (string, optional): Comma-separated list of locations to filter by
- `job_type` (string, optional): Filter by job type (fulltime, parttime, contract, etc.)
- `experience_level` (string, optional): Filter by experience level
- `salary_min` (float, optional): Minimum salary value
- `salary_max` (float, optional): Maximum salary value
- `company` (string, optional): Filter by company name
- `title` (string, optional): Filter by job title
- `specialization` (string, optional): Comma-separated list of specializations to filter by
- `provides_sponsorship` (boolean, optional): Filter by sponsorship availability
- `is_verified` (boolean, optional): Filter by verification status
- `excluded_job_ids` (string, optional): Comma-separated list of job IDs to exclude

### Example Response
```json
{
  "jobs": [
    {
      "id": "uuid-here",
      "title": "Senior Backend Engineer",
      "company": "TechCorp",
      "logo": "https://example.com/logo.png",
      "company_description": "Leading tech company",
      "location": "San Francisco, CA",
      "salary_min_range": 150000.0,
      "salary_max_range": 200000.0,
      "salary_currency": "USD",
      "job_type": "fulltime",
      "description": "We are looking for a senior backend engineer...",
      "posted_date": "2024-01-15T10:00:00Z",
      "experience_level": "senior",
      "specialization": "backend",
      "responsibilities": ["Lead development", "Mentor team"],
      "requirements": ["5+ years experience", "Python expertise"],
      "job_url": "https://techcorp.com/careers",
      "skills": ["Python", "Django", "PostgreSQL"],
      "short_responsibilities": "Lead development, mentor team",
      "short_qualifications": "5+ yrs exp, Python",
      "is_remote": false,
      "is_verified": true,
      "is_sponsored": false,
      "provides_sponsorship": true,
      "expired": false,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z"
    }
  ],
  "hasMore": true,
  "lastJobId": "uuid-here"
}
```

## 2. Get Filtered Jobs Count

**Endpoint:** `GET /api/jobs/filtered-count`

**Description:** Get count of jobs matching the filters

### Request
```
GET http://localhost:8000/jobs/filtered-count?location=San Francisco&job_type=fulltime&salary_min=100000&exclude_applied_count=5
```

### Query Parameters
- All the same filters as paginated endpoint
- `exclude_applied_count` (int): Number of applied jobs to subtract

### Example Response
```json
42
```

## 3. Get Total Available Jobs Count

**Endpoint:** `GET /api/jobs/total-available-count`

**Description:** Get total count of available (non-expired) jobs

### Request
```
GET http://localhost:8000/jobs/total-available-count?exclude_applied_count=10
```

### Query Parameters
- `exclude_applied_count` (int, optional): Number of applied jobs to subtract

### Example Response
```json
150
```

## 4. Get Jobs Bulk

**Endpoint:** `GET /api/jobs/bulk`

**Description:** Get multiple jobs by their IDs

### Request
```
GET http://localhost:8000/jobs/bulk?job_ids=uuid1,uuid2,uuid3
```

### Query Parameters
- `job_ids` (string, required): Comma-separated list of job IDs

### Example Response
```json
[
  {
    "id": "uuid1",
    "title": "Senior Backend Engineer",
    "company": "TechCorp",
    // ... other job fields
  },
  {
    "id": "uuid2",
    "title": "Frontend Developer",
    "company": "StartupInc",
    // ... other job fields
  },
  null  // job not found or expired
]
```

## 5. Get Single Job

**Endpoint:** `GET /api/jobs/{job_id}`

**Description:** Get a single job by ID

### Request
```
GET http://localhost:8000/jobs/uuid-here
```

### Example Response
```json
{
  "id": "uuid-here",
  "title": "Senior Backend Engineer",
  "company": "TechCorp",
  "logo": "https://example.com/logo.png",
  "company_description": "Leading tech company",
  "location": "San Francisco, CA",
  "salary_min_range": 150000.0,
  "salary_max_range": 200000.0,
  "salary_currency": "USD",
  "job_type": "fulltime",
  "description": "We are looking for a senior backend engineer...",
  "posted_date": "2024-01-15T10:00:00Z",
  "experience_level": "senior",
  "specialization": "backend",
  "responsibilities": ["Lead development", "Mentor team"],
  "requirements": ["5+ years experience", "Python expertise"],
  "job_url": "https://techcorp.com/careers",
  "skills": ["Python", "Django", "PostgreSQL"],
  "short_responsibilities": "Lead development, mentor team",
  "short_qualifications": "5+ yrs exp, Python",
  "is_remote": false,
  "is_verified": true,
  "is_sponsored": false,
  "provides_sponsorship": true,
  "expired": false,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

## 6. Get Jobs List (Legacy)

**Endpoint:** `GET /api/jobs/`

**Description:** Get jobs with offset-based pagination (legacy endpoint)

### Request
```
GET http://localhost:8000/jobs/?limit=20&offset=0
```

### Query Parameters
- `limit` (int, 1-100): Number of jobs to return (default: 20)
- `offset` (int, >=0): Number of jobs to skip (default: 0)

### Example Response
```json
[
  {
    "id": "uuid-here",
    "title": "Senior Backend Engineer",
    // ... other job fields
  }
]
```

## Postman Collection Examples

### 1. Basic Job Search
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 10
  - location: San Francisco,New York
  - job_type: fulltime
```

### 2. Search by Skills
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 15
  - q: python react
  - sort_by: salary_max_range
  - sort_order: desc
```

### 3. Multiple Locations
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 20
  - location: San Francisco,New York,Remote
  - salary_min: 150000
  - salary_max: 300000
  - provides_sponsorship: true
  - sort_by: salary_max_range
  - sort_order: desc
```

### 4. Multiple Specializations
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 15
  - specialization: backend,frontend,fullstack
  - experience_level: senior
  - sort_by: created_at
  - sort_order: desc
```

### 5. Company Search
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 10
  - q: Google
  - is_verified: true
  - sort_by: created_at
  - sort_order: desc
```

### 6. Skills-Based Search
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 20
  - q: aws docker kubernetes
  - sort_by: score
  - sort_order: desc
```

### 7. Combined Search and Filter
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 15
  - q: machine learning
  - location: San Francisco,Remote
  - specialization: ml_ai,data_science
  - job_type: fulltime
  - experience_level: senior
  - sort_by: salary_max_range
  - sort_order: desc
```

### 8. Pagination Example
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 5
  - sort_by: created_at
  - sort_order: desc
```

Then use the `lastJobId` from the response for the next page:
```
Method: GET
URL: http://localhost:8000/jobs/paginated
Query Params:
  - limit: 5
  - last_job_id: [lastJobId from previous response]
  - sort_by: created_at
  - sort_order: desc
```

## Testing Scenarios

### 1. Pagination Testing
1. Get first page: `GET /api/jobs/paginated?limit=5`
2. Use `lastJobId` from response to get next page
3. Continue until `hasMore` is false

### 2. Filter Testing
1. Test each filter individually
2. Test multiple filters combined
3. Test edge cases (empty strings, invalid values)

### 3. Error Testing
1. Test with invalid job IDs
2. Test with non-existent jobs
3. Test with expired jobs
4. Test with invalid query parameters

### 4. Performance Testing
1. Test with large limit values
2. Test with many filters
3. Test bulk operations with many job IDs

## Common Filter Values

### Job Types
- `fulltime`
- `parttime`
- `contract`
- `temporary`
- `internship`

### Experience Levels
- `internship`
- `entry`
- `junior`
- `associate`
- `mid-senior`

### Locations
- `San Francisco, CA`
- `New York, NY`
- `Remote`
- `Toronto, Ontario`
- `Vancouver, British Columbia`

### Specializations
- `backend`
- `frontend`
- `fullstack`
- `mobile`
- `devops`
- `data_science`
- `ml_ai`
- `product`
- `ux_ui`
- `qa`
- `security`
- `cloud`
- `blockchain`
- `game_dev`
- `ar_vr`
- `embedded`
- `iot`
- `robotics`
- `fintech`
- `healthtech`
- `edtech`
- `ecommerce`
- `martech`
- `enterprise` 