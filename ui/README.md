# Lab AI - React Frontend

A modern React SPA for the Lab AI processing system, built with Vite, TypeScript, and Tailwind CSS.

## Features

### 📥 **Inbox Page**
- **File Upload**: Drag & drop or click to upload PDF lab reports
- **URL Submission**: Process reports from public URLs
- **Configuration Presets**: Default, High Quality, Fast Processing modes
- **Advanced Settings**: Custom DPI, scoring thresholds, image extraction

### 📋 **Queue Page**
- **Real-time Status**: Auto-updating job status with progress bars
- **Progress Tracking**: Detailed pipeline stage information
- **Job Management**: Cancel queued/processing jobs
- **Status Filtering**: Filter by queued, processing, completed, failed, cancelled

### 📊 **Processed Results**
- **Search & Filter**: Find results by filename, job ID, confidence scores
- **Quality Metrics**: Document scores, review flags, confidence distributions
- **Batch Operations**: Download multiple results, bulk actions
- **Statistical Overview**: Success rates, processing times, quality trends

### 👁️ **Viewer Page**
- **Left Panel**: Extracted text with page navigation and thumbnails
- **Right Panel**: Hierarchical JSON view (Patient → Specimens → Panels → Tests)
- **Confidence Highlighting**: Visual indicators for low-confidence fields
- **Interactive Navigation**: Click between panels and tests
- **Export Options**: Download processed JSON results

### ✏️ **Manual Review Page**
- **Editable Forms**: Click-to-edit interface for test fields
- **Field-level Corrections**: Edit test names, values, units, reference ranges
- **Confidence Analysis**: Detailed breakdown of field quality issues
- **Save Corrections**: Store fixes to `/data/expected/<job_id>.json`
- **Training Data**: Generate annotations for ML model improvement
- **Change Tracking**: Visual diff of original vs corrected data

### 🔍 **Compare Page**
- **Side-by-side Diff**: Visual comparison of original vs corrected results
- **File Status Indicators**: Shows availability of both original and corrected files
- **Deep Object Diff**: Highlights added, removed, and modified fields at any level
- **Golden Set Promotion**: One-click button to promote corrections to golden dataset
- **Statistical Summary**: Count of changes by type (added/removed/modified)
- **Download Options**: Export both original and corrected versions

## Technology Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for utility-first styling
- **React Query** for server state management
- **React Router** for client-side routing
- **Axios** for API communication
- **React Hot Toast** for notifications
- **React JSON Tree** for JSON visualization
- **React Dropzone** for file uploads
- **Lucide React** for consistent icons

## Development

### Prerequisites
- Node.js 18+
- npm or yarn

### Setup
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

### Environment Variables

Create a `.env.local` file:
```env
VITE_API_URL=http://localhost:8000
```

### Development Server
The dev server runs on `http://localhost:3000` with:
- **Hot Module Replacement** for instant updates
- **API Proxy** to backend at `/api/*` → `http://localhost:8000/*`
- **TypeScript checking** and error reporting
- **ESLint integration** for code quality

## Production Deployment

### Docker Build
```bash
# Build production image
docker build -t lab-ai-ui .

# Run container
docker run -p 80:80 lab-ai-ui
```

### Docker Compose
```yaml
ui:
  build: ./ui
  ports:
    - "3000:80"
  environment:
    - API_URL=http://api:8000
  depends_on:
    - api
```

### Manual Build
```bash
# Build for production
npm run build

# Serve with any static server
npx serve -s dist -l 3000
```

## Architecture

### State Management
- **React Query** for server state (jobs, results, system status)
- **React Context** for global UI state
- **Local State** for form data and UI interactions

### Routing Structure
```
/                   → Redirect to /inbox
/inbox             → File upload and job submission
/queue             → Job status monitoring
/processed         → Completed results with search/filter
/viewer/:jobId     → Read-only result visualization
/review/:jobId     → Manual review and correction interface
/compare/:jobId    → Side-by-side diff and golden set promotion
```

### API Integration
- **Automatic retries** with exponential backoff
- **Request/response interceptors** for error handling
- **Polling utilities** for job status updates
- **File upload progress** tracking
- **Optimistic updates** for better UX

### Component Architecture
```
App
├── Layout (navigation, header, system status)
├── Pages
│   ├── InboxPage (upload forms, config selection)
│   ├── QueuePage (job list, status polling)
│   ├── ProcessedPage (results table, filters)
│   ├── ViewerPage (split view: text + JSON)
│   ├── ReviewPage (editable forms, corrections)
│   └── ComparePage (diff viewer, golden set promotion)
├── Components (reusable UI elements)
├── Hooks (custom React hooks)
├── Services (API layer)
├── Types (TypeScript definitions)
└── Utils (helper functions)
```

### Styling System
- **Tailwind CSS** for utility classes
- **Custom CSS Components** for common patterns
- **Consistent Design System** with color palette
- **Responsive Design** for mobile/tablet support
- **Dark Mode Ready** (theme variables defined)

### Performance Optimizations
- **Code Splitting** with dynamic imports
- **Lazy Loading** for non-critical routes
- **Memoized Components** to prevent re-renders
- **Virtualized Lists** for large datasets
- **Image Optimization** with modern formats
- **Bundle Splitting** for optimal caching

## Key Features Deep Dive

### Real-time Job Monitoring
- WebSocket-like experience using polling
- Progress bars with stage-specific updates
- Automatic retry on network errors
- Optimistic UI updates

### Confidence-based Quality Assessment
- Visual indicators for low confidence fields
- Detailed breakdown of scoring components
- Interactive confidence threshold controls
- Quality-based filtering and sorting

### Manual Review Workflow
1. **Load processed results** with confidence scores
2. **Identify issues** through visual highlighting
3. **Edit fields** with click-to-edit interface
4. **Save corrections** to expected results
5. **Generate training data** for model improvement

### Golden Set Workflow
1. **Compare results** using side-by-side diff viewer
2. **Review changes** between original and corrected versions
3. **Validate corrections** are accurate and complete
4. **Promote to golden** set with one-click button
5. **Golden files** stored in `/data/golden/` with metadata
6. **Used for evaluation** and model performance benchmarking

### File Management
- **Drag & drop uploads** with progress indication
- **File validation** (PDF only, size limits)
- **Batch processing** support
- **URL fetching** for remote files
- **Download management** for results

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Follow TypeScript best practices
2. Use Tailwind classes over custom CSS
3. Write accessible components (ARIA labels)
4. Add error boundaries for crash protection
5. Include loading states for better UX
6. Test on multiple screen sizes
7. Follow the established routing patterns

## Security Considerations

- **Input validation** on all form fields
- **XSS protection** with sanitized outputs
- **CSRF protection** via headers
- **Content Security Policy** in nginx config
- **File type validation** for uploads
- **URL validation** for external links

## Future Enhancements

- **WebSocket support** for real-time updates
- **Offline mode** with service workers
- **Advanced search** with Elasticsearch
- **Batch operations** for bulk processing
- **User management** and authentication
- **Audit trails** for review sessions
- **Custom dashboards** for analytics
- **Mobile app** with React Native
- **Keyboard shortcuts** for power users
- **Accessibility improvements** (screen readers)

The UI provides a complete interface for lab report processing with professional-grade features for quality assessment, manual review, and system monitoring.