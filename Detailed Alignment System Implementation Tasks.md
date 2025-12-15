## Phase 8: Model Alignment System Refactoring

### Task A1: Integrate AlignmentUI with Model Cache
**Priority**: High
**Status**: Pending
**Estimated Effort**: 2-3 hours

#### Detailed Requirements:
1. **Update AlignmentUI Component** (`stages/display_buildings/src/components/ui/AlignmentUI.tsx`)
   - Replace direct model loading with `modelsCache.getModel()`
   - Add loading states and error handling for cache operations
   - Implement model disposal on component unmount

2. **Update AlignmentStage Component** (`stages/display_buildings/src/stage/ui/AlignmentStage.tsx`)
   - Integrate with model cache for loading aligned models
   - Add cache-aware model rendering with proper cleanup
   - Implement fallback to direct loading if cache fails

3. **Update AlignedModel Component** (to be created)
   - Design component to work with cached models
   - Implement transformation application on cached model instances
   - Add visual feedback for model loading states

4. **Remove Duplicate Loading Code**
   - Identify and remove duplicate FBX loading logic
   - Consolidate all model loading through `modelsCache`
   - Update imports and dependencies

#### Technical Implementation:
```typescript
// Example: Updated AlignmentUI model loading
const loadModelForAlignment = async (modelUUID: string) => {
  try {
    setIsLoading(true);
    const model = await modelsCache.getModel(modelUUID);
    setCurrentModel(model);
  } catch (error) {
    console.error('Failed to load model from cache:', error);
    // Fallback to direct loading if needed
  } finally {
    setIsLoading(false);
  }
};
```

#### Success Criteria:
- [ ] All alignment components use `modelsCache.getModel()`
- [ ] No duplicate FBX loading code exists
- [ ] Proper error handling and fallback mechanisms
- [ ] Memory management with model disposal

---

### Task A2: Implement Alignment Mode Transition
**Priority**: High  
**Status**: Pending  
**Estimated Effort**: 3-4 hours

#### Detailed Requirements:
1. **Redux Store Enhancement**
   - Add `isAlignmentMode` boolean to alignmentSlice
   - Create actions: `enterAlignmentMode`, `exitAlignmentMode`
   - Add selectors: `getIsAlignmentMode`, `getAlignmentModeState`

2. **StartAlignmentButton Enhancement**
   - Connect button to `enterAlignmentMode` action
   - Add visual feedback during mode transition
   - Disable button during transition

3. **Camera System Updates**
   - Create `AlignmentCameraSetup` utility
   - Implement automatic camera positioning for alignment
   - Configure camera controls for alignment mode

4. **UI State Management**
   - Show/hide components based on alignment mode
   - Update control panels for alignment context
   - Preserve view state when switching modes

#### Technical Implementation:
```typescript
// alignmentSlice.ts additions
interface AlignmentState {
  isAlignmentMode: boolean;
  alignmentModeData: {
    initialTransform: ModelTransform | null;
    selectedPolygons: Building[];
    modelUUID: string | null;
  };
}

// Actions
enterAlignmentMode: (state, action: PayloadAction<{
  modelUUID: string;
  polygons: Building[];
  initialTransform?: ModelTransform;
}>) => {
  state.isAlignmentMode = true;
  state.alignmentModeData = {
    modelUUID: action.payload.modelUUID,
    selectedPolygons: action.payload.polygons,
    initialTransform: action.payload.initialTransform || null,
  };
};

// StartAlignmentButton update
const handleStartAlignment = () => {
  if (canStartAlignment && modelUUID && selectedPolygons.length > 0) {
    dispatch(enterAlignmentMode({
      modelUUID,
      polygons: selectedPolygons,
    }));
    // Trigger initial transform calculation
    dispatch(prepareInitialTransform({ modelUUID, polygons: selectedPolygons }));
  }
};
```

#### Success Criteria:
- [ ] Smooth transition between view and alignment modes
- [ ] Automatic camera setup for alignment
- [ ] UI correctly shows/hides based on mode
- [ ] State preserved during mode switches

---

### Task A3: Improve Model/Polygon Selection Interface
**Priority**: Medium  
**Status**: Pending  
**Estimated Effort**: 4-5 hours

#### Detailed Requirements:
1. **Enhanced BuildingSelection Component**
   - Add visual feedback for selected polygons (highlight, animation)
   - Implement multi-select with shift/ctrl keys
   - Add polygon counter and selection summary

2. **Model Selection Component**
   - Create `ModelSelector` component
   - Display available models with thumbnails/metadata
   - Add search and filter functionality
   - Show model compatibility information

3. **Selection Validation**
   - Add validation rules (min polygons, model compatibility)
   - Provide clear error messages
   - Visual indicators for validation state

4. **Workflow Improvements**
   - Streamline add/remove process
   - Add "clear selection" functionality
   - Implement selection persistence

#### UI Mockup Components:
```typescript
// ModelSelector component structure
interface ModelSelectorProps {
  availableModels: ModelMetadata[];
  selectedModelId: string | null;
  onSelect: (modelId: string) => void;
  onUploadNew?: () => void;
}

// Enhanced BuildingSelection
interface EnhancedBuildingSelectionProps {
  buildings: Building[];
  selectedPolygons: Building[];
  onPolygonSelect: (polygon: Building, isSelected: boolean) => void;
  onClearSelection: () => void;
  validationErrors: string[];
}
```

#### Success Criteria:
- [ ] Intuitive polygon selection with visual feedback
- [ ] Comprehensive model selection interface
- [ ] Clear validation and error messages
- [ ] Streamlined workflow for adding elements

---

### Task A4: Model Management API Implementation (CRITICAL)
**Priority**: CRITICAL  
**Status**: Pending  
**Estimated Effort**: 6-8 hours

#### Backend API Requirements:

1. **Database Schema** (PostgreSQL example):
```sql
-- models table
CREATE TABLE models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_format VARCHAR(10) NOT NULL CHECK (file_format IN ('fbx', 'obj', 'gltf', 'glb')),
  file_size BIGINT NOT NULL,
  vertex_count INTEGER,
  face_count INTEGER,
  bounding_box JSONB,
  metadata JSONB DEFAULT '{}',
  is_linked BOOLEAN DEFAULT FALSE,
  linked_building_id UUID REFERENCES buildings(id),
  created_by VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP WITH TIME ZONE
);

-- model_tags table for categorization
CREATE TABLE model_tags (
  id SERIAL PRIMARY KEY,
  model_id UUID REFERENCES models(id) ON DELETE CASCADE,
  tag VARCHAR(50) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_models_is_linked ON models(is_linked);
CREATE INDEX idx_models_created_at ON models(created_at);
CREATE INDEX idx_model_tags_model_id ON model_tags(model_id);
CREATE INDEX idx_model_tags_tag ON model_tags(tag);
```

2. **API Endpoints** (`stages/serve_buildings/index.js`):
```javascript
// GET /api/models - List models with pagination and filtering
fastify.get('/api/models', async (request, reply) => {
  const { 
    page = 1, 
    limit = 20, 
    search, 
    format, 
    isLinked,
    tags 
  } = request.query;
  
  // Implementation with database query
});

// GET /api/models/:id - Get model details
fastify.get('/api/models/:id', async (request, reply) => {
  const { id } = request.params;
  // Implementation
});

// POST /api/models - Create model record
fastify.post('/api/models', async (request, reply) => {
  const modelData = request.body;
  // Implementation with file handling
});

// PUT /api/models/:id - Update model
fastify.put('/api/models/:id', async (request, reply) => {
  const { id } = request.params;
  const updates = request.body;
  // Implementation
});

// DELETE /api/models/:id - Soft delete model
fastify.delete('/api/models/:id', async (request, reply) => {
  const { id } = request.params;
  // Implementation
});

// GET /api/models/unlinked - Get unlinked models
fastify.get('/api/models/unlinked', async (request, reply) => {
  // Implementation
});

// POST /api/models/:id/link - Link model to building
fastify.post('/api/models/:id/link', async (request, reply) => {
  const { id } = request.params;
  const { buildingId } = request.body;
  // Implementation
});
```

3. **File Storage Structure**:
```
public/models/
├── {uuid}.fbx              # Original model file
├── {uuid}_thumbnail.png    # Generated thumbnail
└── {uuid}_metadata.json    # Extracted metadata
```

#### Frontend Implementation:

1. **Redux Slice** (`src/store/slices/modelsSlice.ts`):
```typescript
interface ModelsState {
  models: ModelRecord[];
  currentModel: ModelRecord | null;
  loading: boolean;
  error: string | null;
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
  filters: {
    search: string;
    format: string | null;
    isLinked: boolean | null;
    tags: string[];
  };
}

// Actions: fetchModels, fetchModelById, createModel, updateModel, deleteModel, linkModel
// Thunks: API calls with proper error handling
```

2. **UI Components**:
   - `ModelsTable`: Data table with sorting, filtering, pagination
   - `ModelDetailsModal`: Detailed view with metadata and actions
   - `ModelUploadWizard`: Multi-step upload form
   - `UnlinkedModelsView`: Specialized view for unlinked models
   - `ModelLinkDialog`: Interface for linking models to buildings

3. **Integration Points**:
   - Update `modelUploadSlice` to create model records after upload
   - Connect `BuildingSelection` to model listing
   - Add model management to admin/settings interface

#### Success Criteria:
- [ ] Complete RESTful API for model management
- [ ] Database schema with proper relationships
- [ ] Frontend Redux slice with all CRUD operations
- [ ] Comprehensive UI components for model management
- [ ] Integration with existing upload system
- [ ] Ability to view and manage unlinked models

---

## Dependencies and Sequencing

### Phase 8 Task Dependencies:
```
A4 (API) → A1 (Cache Integration)
     ↓
A2 (Mode Transition) → A3 (UI Improvements)
```

### Recommended Execution Order:
1. **Start with A4 (API)** - Foundation for other tasks
2. **Parallel execution**:
   - Backend: Implement API endpoints and database
   - Frontend: Create modelsSlice and basic components
3. **Then A1 (Cache Integration)** - Requires API for model metadata
4. **Then A2 (Mode Transition)** - Requires cache integration
5. **Finally A3 (UI Improvements)** - Polishing after core functionality

### Integration Points with Existing System:
- **Current Upload System**: Extend to create model records
- **Building Data**: Link models to buildings via API
- **Alignment System**: Use model metadata for compatibility checks
- **Cache System**: Preload models based on usage patterns

## Testing Requirements

### Backend Tests:
- [ ] API endpoint unit tests
- [ ] Database integration tests
- [ ] File upload/download tests
- [ ] Error handling tests

### Frontend Tests:
- [ ] Component unit tests
- [ ] Redux slice tests
- [ ] Integration tests with API
- [ ] UI interaction tests

### End-to-End Tests:
- [ ] Complete model upload workflow
- [ ] Model selection and alignment
- [ ] Model management operations
- [ ] Mode transition scenarios

## Documentation Requirements

### API Documentation:
- [ ] OpenAPI/Swagger specification
- [ ] Endpoint descriptions and examples
- [ ] Authentication/authorization requirements
- [ ] Error code documentation

### User Documentation:
- [ ] Model upload guide
- [ ] Alignment workflow instructions
- [ ] Model management tutorial
- [ ] Troubleshooting guide

### Developer Documentation:
- [ ] Architecture overview
- [ ] Code organization
- [ ] Extension points
- [ ] Testing guide

## Risk Mitigation

### Technical Risks:
1. **FBX Loading Performance**: Implement progressive loading and LOD
2. **Memory Management**: Add model disposal and cache limits
3. **Database Scalability**: Use pagination and efficient queries
4. **File Storage**: Implement cleanup and storage limits

### UX Risks:
1. **Complex Workflow**: Provide clear guidance and defaults
2. **Learning Curve**: Add tooltips and inline help
3. **Error Recovery**: Implement undo/redo and auto-save

### Deployment Risks:
1. **Database Migration**: Use migration scripts
2. **File System Permissions**: Document requirements
3. **Backward Compatibility**: Maintain existing API endpoints

## Success Metrics

### Quantitative:
- [ ] Model upload success rate > 95%
- [ ] Alignment completion rate > 80%
- [ ] API response time < 500ms
- [ ] Cache hit rate > 70%

### Qualitative:
- [ ] User satisfaction with model selection interface
- [ ] Ease of alignment workflow
- [ ] Clarity of error messages
- [ ] Overall system reliability

---

*Last Updated: Phase 8 Planning*
*Next Review: After A4 (API) implementation*
*