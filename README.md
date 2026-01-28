# Livinit - AI Interior Design Platform

A complete Next.js 14+ application with integrated FastAPI backend for AI-powered interior design automation.

## 🚀 Features

- **USDZ Upload & Processing**: Upload room USDZ files with real-time preview
- **AI Pipeline**: Automated furniture selection, layout generation, and 3D rendering
- **Real-time Progress**: Server-Sent Events for live pipeline progress tracking
- **3D Visualization**: Advanced model viewer with fallback support
- **Cost Management**: Budget-aware furniture selection with cost tracking
- **Layout Optimization**: VLM-based layout optimization with visual feedback

## 🏗️ Architecture

### Frontend (Next.js 14+)
- **Framework**: Next.js 14+ with App Router and TypeScript
- **Styling**: Tailwind CSS with custom design system
- **3D Rendering**: model-viewer with dependency injection pattern
- **State Management**: Custom hooks with clean architecture
- **API Integration**: Type-safe API client with error handling

### Backend (FastAPI)
- **Framework**: FastAPI with async/await support
- **Pipeline**: LangGraph-based furniture selection and layout pipeline
- **AI Models**: LLM for asset selection, VLM for layout optimization
- **File Processing**: USDZ parsing, 3D rendering, image generation
- **Streaming**: Server-Sent Events for real-time progress

## 🚀 Quick Start

### Development Mode (Recommended)
```bash
# Install frontend dependencies
npm install

# Start both frontend and backend
npm run full-dev
```

This starts:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Frontend Only
```bash
npm install
npm run dev
```

### Backend Only
```bash
npm run backend
# OR manually:
cd livinit_pipeline-main
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python api.py
```

## 📁 Project Structure

```
livinit-web/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # Root layout with global config
│   ├── page.tsx                 # Main application orchestrator
│   └── globals.css              # Global styles and model-viewer config
├── components/                   # React components
│   ├── Navigation.tsx           # Top navigation bar
│   ├── FilterSection.tsx        # Room filters (type, dimensions, budget)
│   ├── DesignInput.tsx          # User input for design intent
│   ├── FileUploadModal.tsx      # USDZ file upload interface
│   ├── RoomView.tsx             # 3D model viewer and results display
│   ├── ChatInterface.tsx        # Chat UI with pipeline results
│   └── PipelineProgressModal.tsx # Real-time pipeline progress
├── services/                     # Service layer
│   ├── ApiClient.ts             # HTTP client for backend API
│   └── ModelViewerService.ts    # 3D model rendering service
├── hooks/                        # Custom React hooks
│   ├── usePipeline.ts           # Pipeline execution and state
│   └── useModelViewer.ts        # 3D model viewer management
├── types/                        # TypeScript definitions
│   ├── global.d.ts              # Global type declarations
│   └── model-viewer.d.ts        # Model-viewer component types
├── livinit_pipeline-main/        # Backend FastAPI application
│   ├── api.py                   # Main FastAPI application
│   ├── pipeline/                # AI pipeline nodes and logic
│   ├── LayoutVLM/              # Vision-Language Model for layout
│   └── requirements.txt         # Python dependencies
└── scripts/
    └── start-backend.sh         # Backend startup script
```

## 🔄 Complete Flow

### 1. User Input
1. User enters design intent (e.g., "Modern minimalist living room")
2. Sets budget and room parameters
3. Clicks "Generate Design"

### 2. USDZ Upload
1. Upload modal appears for USDZ room file
2. File validated and uploaded to backend via `/upload/room`
3. Backend returns `usdz_path` for pipeline processing

### 3. AI Pipeline Execution
1. Frontend calls `/pipeline` with SSE for real-time progress
2. Backend runs AI pipeline:
   - **Asset Selection**: AI selects furniture within budget
   - **Layout Generation**: LLM creates initial furniture placement
   - **Layout Optimization**: VLM optimizes positions and constraints
   - **3D Rendering**: Generates final USDZ with furniture placed

### 4. Result Presentation
1. Pipeline completion triggers result download
2. Frontend fetches:
   - Final USDZ file with furniture
   - Layout preview images (initial, refined, optimized)
   - Top-down and perspective renders
   - Optimization process GIF
3. Results displayed in 3D viewer and chat interface

## 🛠️ API Integration Details

### Request Flow
```typescript
// 1. Upload USDZ
const uploadResponse = await apiClient.uploadRoom(file)

// 2. Configure pipeline
const request: PipelineRequest = {
  user_intent: "Modern minimalist living room",
  budget: 5000,
  usdz_path: uploadResponse.data.usdz_path,
  run_select_assets: true,
  run_initial_layout: true,
  run_refine_layout: true,
  run_layoutvlm: true,
  run_render_scene: true
}

// 3. Execute with progress tracking
const result = await apiClient.runPipeline(request, onEvent, onError)

// 4. Download results
const finalUsdz = await apiClient.downloadUSDZ(result.run_dir)
```

### SSE Events
- **start**: Pipeline initiated with node list
- **node_start**: Individual node execution begins
- **node_progress**: Progress within current node
- **node_complete**: Node finished with results
- **complete**: Pipeline finished successfully
- **error**: Execution failed with error details

### Error Handling
- **Network errors**: Connection issues, timeouts
- **Validation errors**: Invalid file formats, missing parameters
- **Pipeline errors**: AI model failures, resource constraints
- **Recovery**: Automatic retry, graceful degradation, user feedback

## 🧪 Testing

### Build Verification
```bash
npm run build       # Verify production build
npm run type-check  # TypeScript validation
npm run lint        # Code quality checks
```

### Full Integration Test
```bash
# 1. Start backend
npm run backend

# 2. Start frontend
npm run dev

# 3. Test complete flow:
#    - Upload USDZ file
#    - Enter design intent
#    - Monitor pipeline progress
#    - Verify results display
```

## 🚀 Production Deployment

### Environment Variables
```bash
# Frontend
NEXT_PUBLIC_API_BASE_URL=https://api.livinit.com

# Backend
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...
SUPABASE_KEY=...
```

### Frontend Deployment (Vercel/Netlify)
```bash
npm run build
# Deploy dist/ folder
```

### Backend Deployment (Docker)
```bash
cd livinit_pipeline-main
docker build -t livinit-api .
docker run -p 8000:8000 livinit-api
```

## 🔧 Configuration

### API Configuration
- Base URL configurable via environment
- Timeout settings
- CORS configuration for production

### 3D Viewer Configuration
- USDZ handling with iOS Quick Look fallback
- Model-viewer settings
- Loading timeout and error recovery

### Pipeline Configuration
- Enable/disable specific pipeline stages
- Budget constraints
- Asset selection criteria

## 📊 Monitoring

### Logs
- Structured logging in both frontend and backend
- Pipeline execution tracking
- Performance metrics

### Health Checks
- `/health` endpoint for load balancer monitoring
- Frontend build verification
- API connectivity tests

## 🔐 Security

### Input Validation
- File format validation
- Size limits on uploads
- Parameter sanitization

### CORS Configuration
```typescript
// Development
allow_origins: ["*"]

// Production
allow_origins: ["https://livinit.com", "https://app.livinit.com"]
```

## 📈 Performance

### Optimizations
- Lazy loading of 3D models
- Image optimization (consider next/image)
- SSE instead of polling for better performance
- Caching strategies for API responses

### Benchmarks
- Pipeline execution: ~2-5 minutes depending on complexity
- USDZ upload: <10 seconds for typical room files
- 3D model loading: <5 seconds with model-viewer

## 🧩 Extensibility

### Adding New Pipeline Nodes
1. Implement node in `pipeline/nodes/`
2. Register in `api.py` NODES dictionary
3. Update frontend types and progress tracking

### Custom 3D Viewers
1. Implement new viewer in `ModelViewerService`
2. Add format detection
3. Update component props and rendering logic

### Additional File Formats
1. Extend `ApiClient` upload methods
2. Update backend file validation
3. Add viewer support in frontend

This integration provides a scalable, maintainable foundation for AI-powered interior design with real-time feedback and professional 3D visualization capabilities.

