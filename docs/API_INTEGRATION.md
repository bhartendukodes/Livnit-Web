# API Integration Documentation

## Overview

This document explains the complete integration between the Next.js frontend and the FastAPI backend for the Livinit Interior Design AI system.

## Architecture

### Backend API (FastAPI)
- **Location**: `livinit_pipeline-main/api.py`
- **Port**: 8000 (default)
- **Features**: USDZ upload, pipeline execution with SSE, result downloads

### Frontend (Next.js 14+)
- **Framework**: Next.js 14+ with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Architecture**: Clean Architecture with Dependency Injection

## API Endpoints

### 1. File Upload
```
POST /upload/room
```
- **Purpose**: Upload USDZ room file
- **Input**: FormData with USDZ file
- **Output**: `{ status: "success", data: { usdz_path: string } }`

### 2. Pipeline Execution
```
POST /pipeline
```
- **Purpose**: Run complete interior design pipeline
- **Input**: PipelineRequest (JSON)
- **Output**: Server-Sent Events (SSE) stream
- **Events**: start, node_start, node_progress, node_complete, complete, error

### 3. Result Downloads
```
GET /download/usdz/{run_dir}     - Final USDZ with furniture
GET /preview/{run_dir}           - Initial layout preview
GET /preview-refine/{run_dir}    - Refined layout preview
GET /preview-post/{run_dir}      - Post-optimization preview
GET /render/{run_dir}/top        - Top view render
GET /render/{run_dir}/perspective - Perspective view render
GET /layoutvlm-gif/{run_dir}     - Optimization GIF
```

## Frontend Architecture

### Services Layer
- **ApiClient** (`services/ApiClient.ts`): HTTP client with error handling
- **ModelViewerService** (`services/ModelViewerService.ts`): 3D model rendering

### Hooks Layer
- **usePipeline** (`hooks/usePipeline.ts`): Pipeline state management
- **useModelViewer** (`hooks/useModelViewer.ts`): 3D model viewing

### Components Layer
- **Main Page** (`app/page.tsx`): Orchestrates entire flow
- **RoomView** (`components/RoomView.tsx`): 3D model display
- **ChatInterface** (`components/ChatInterface.tsx`): User interaction
- **PipelineProgressModal** (`components/PipelineProgressModal.tsx`): Real-time progress

## Pipeline Flow

### 1. User Input
```typescript
// User enters design intent and selects budget
const userIntent = "Modern minimalist living room"
const budget = 5000
```

### 2. File Upload
```typescript
// Upload USDZ room file
const uploadResponse = await apiClient.uploadRoom(file)
const usdzPath = uploadResponse.data.usdz_path
```

### 3. Pipeline Execution
```typescript
// Run pipeline with SSE progress tracking
const request: PipelineRequest = {
  user_intent: userIntent,
  budget: budget,
  usdz_path: usdzPath,
  run_rag_scope: false,
  run_select_assets: true,
  run_initial_layout: true,
  run_refine_layout: true,
  run_layoutvlm: true,
  run_render_scene: true
}

await apiClient.runPipeline(request, onEvent, onError)
```

### 4. Result Processing
```typescript
// Download generated USDZ and preview images
const finalUsdz = await apiClient.downloadUSDZ(result.run_dir)
const topView = await apiClient.getRender(result.run_dir, 'top')
const perspectiveView = await apiClient.getRender(result.run_dir, 'perspective')
```

## Pipeline Stages

### Backend Pipeline Nodes
1. **extract_room** - Extract room geometry from uploaded USDZ
2. **rag_scope_assets** - Load and scope furniture assets by user intent
3. **select_assets** - LLM selects furniture within budget constraints
4. **validate_and_cost** - Validate selection and compute total cost
5. **initial_layout** - LLM generates initial furniture placement
6. **layout_preview** - Render layout preview image
7. **refine_layout** - Analyze layout issues and generate constraints
8. **layout_preview_refine** - Render refined layout preview
9. **layoutvlm** - VLM-based layout optimization solver
10. **render_scene** - Render final 3D scene with assets

### Frontend Progress Tracking
- Real-time progress via SSE
- Node-level progress indicators
- Error handling and retry logic
- User-friendly status messages

## Error Handling

### API Errors
- Network connectivity issues
- Invalid file formats
- Pipeline execution failures
- Resource not found errors

### Client-Side Validation
- File format validation (.usdz only)
- Budget range validation
- Required field validation

### Recovery Mechanisms
- Automatic retry for transient failures
- Graceful degradation for optional features
- User-friendly error messages
- Fallback UI states

## USDZ Handling

### Upload Validation
```typescript
if (!file.name.endsWith('.usdz')) {
  throw new Error('Please upload a USDZ file (.usdz)')
}
```

### Preview Rendering
- Uses model-viewer for compatible browsers
- Fallback to file info display for unsupported browsers
- Special handling for iOS Safari (AR Quick Look)

### Download
- Proper MIME type: `model/vnd.usdz+zip`
- Content-Disposition header for correct filename

## Development Setup

### Prerequisites
- Node.js 18+ for frontend
- Python 3.9+ for backend
- Required Python packages (see requirements.txt)

### Frontend Development
```bash
npm install
npm run dev          # Start frontend only
npm run full-dev     # Start both frontend and backend
```

### Backend Development
```bash
cd livinit_pipeline-main
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python api.py
```

## Production Considerations

### Performance
- SSE for real-time progress (better than polling)
- Lazy loading of 3D models
- Image optimization (consider next/image)
- Proper caching headers

### Security
- CORS configuration for production domains
- Input validation and sanitization
- File upload size limits
- Rate limiting

### Scalability
- Stateless API design
- Background processing for long-running pipelines
- CDN for static assets
- Database for persistent state (if needed)

## Testing

### Unit Tests
- API client functionality
- Hook behavior
- Component rendering

### Integration Tests
- Full pipeline flow
- File upload/download
- Error scenarios

### E2E Tests
- User journey from upload to results
- Cross-browser compatibility
- Performance benchmarks

## Monitoring

### Logging
- Structured logging in both frontend and backend
- Pipeline progress tracking
- Error reporting

### Metrics
- Pipeline execution times
- Success/failure rates
- User engagement metrics

## Deployment

### Frontend (Vercel/Netlify)
- Static site generation
- Environment variables for API URL
- CDN distribution

### Backend (AWS/GCP)
- Container deployment (Docker)
- Auto-scaling for variable load
- Health check endpoints