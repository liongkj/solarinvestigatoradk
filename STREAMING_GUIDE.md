# ADK Streaming Implementation Guide

## Overview

This implementation adds real-time streaming support to your Solar Investigation ADK application, allowing the frontend to display agent responses as they are generated word-by-word, following the ADK event streaming patterns.

## Key Features

### 1. Real-time Text Streaming
- **Streaming Text Chunks**: Individual words/phrases streamed as they're generated
- **Partial vs Complete**: Distinguishes between incomplete chunks (`partial: true`) and complete messages
- **Text Accumulation**: Frontend automatically accumulates streaming chunks into complete text

### 2. Event Types Supported
Based on your provided pseudocode pattern:

```typescript
// Event types handled:
- 'streaming_text_chunk'    // Partial text chunks (event.partial = true)
- 'complete_text_message'   // Complete text (event.partial = false)
- 'tool_call_request'       // When agent calls tools
- 'tool_result'             // Tool execution results
- 'other_content'           // Code results, etc.
- 'state_artifact_update'   // State/artifact changes
- 'control_signal'          // Control signals
- 'streaming_error'         // Error handling
```

### 3. Backend Implementation

#### Enhanced Event Handler (`investigation_service_simplified.py`)
```python
async def _handle_streaming_event(self, investigation_id: str, event):
    """Handle ADK streaming events and broadcast to SSE clients"""
    
    # Analyzes each ADK event based on the pseudocode pattern:
    if event.content and event.content.parts:
        if event.get_function_calls():
            # Tool call request
        elif event.get_function_responses():
            # Tool result  
        elif event.content.parts[0].text:
            is_partial = getattr(event, 'partial', False)
            if is_partial:
                # Streaming text chunk
            else:
                # Complete text message
    elif event.actions and (event.actions.state_delta or event.actions.artifact_delta):
        # State/Artifact Update
    else:
        # Control signal or other
```

#### SSE Streaming
- Events are queued in `event_queues` for each investigation
- Frontend connects to `/api/investigations/{id}/stream` endpoint
- Real-time events streamed via Server-Sent Events

### 4. Frontend Implementation

#### Angular Service (`investigation.service.ts`)
```typescript
// Enhanced SSE event interface
export interface SSEEvent {
    type: 'streaming_text_chunk' | 'complete_text_message' | 'tool_call_request' | ...;
    content?: string;
    partial?: boolean;
    tool_calls?: string[];
    // ... other properties
}

// Text accumulation for streaming
private streamingTextAccumulator: Map<string, BehaviorSubject<string>>;

// Process streaming events
private processStreamingEvent(event: SSEEvent): void {
    if (event.type === 'streaming_text_chunk' && event.partial) {
        // Accumulate text chunks
    } else if (event.type === 'complete_text_message' && !event.partial) {
        // Finalize accumulated text
    }
}
```

#### Component Usage (`investigation-detail.component.ts`)
```typescript
// Streaming properties
streamingText$ = this.investigationService.getStreamingText(this.investigationId);
currentStreamingText = '';
isStreaming = false;

// Setup streaming events
private setupSSEStreamingEvents(): void {
    this.streamingText$.pipe(takeUntil(this.destroy$)).subscribe(text => {
        this.currentStreamingText = text;
    });
}

// Handle streaming events
private handleSSEStreamingEvents(event: SSEEvent): void {
    switch (event.type) {
        case 'streaming_text_chunk':
            this.isStreaming = true;
            break;
        case 'complete_text_message':
            this.isStreaming = false;
            break;
        // ... other cases
    }
}
```

#### HTML Template
```html
<!-- Real-time streaming display -->
<div *ngIf="isStreaming || currentStreamingText" class="card mb-4">
    <div class="card-header">
        <h5 class="card-title mb-0">
            <i class="fas fa-stream text-primary me-2"></i>
            Real-time Agent Response
            <span *ngIf="isStreaming" class="spinner-border spinner-border-sm ms-2">
        </h5>
    </div>
    <div class="card-body">
        <div class="streaming-text-container" style="max-height: 200px; overflow-y: auto;">
            <pre class="streaming-text">{{ currentStreamingText || 'Waiting for agent response...' }}</pre>
        </div>
        <div *ngIf="isStreaming" class="text-muted small mt-2">
            <i class="fas fa-clock me-1"></i>
            Agent is responding...
        </div>
    </div>
</div>
```

## Usage Instructions

### 1. Start the Backend
```bash
cd backend
uv run fastapi run src/main.py --host 0.0.0.0 --port 8000
```

### 2. Start the Frontend
```bash
cd frontend
npm start
```

### 3. Test Streaming
1. Navigate to the investigation detail page
2. Start a new investigation
3. Watch the "Real-time Agent Response" card for streaming text
4. Monitor browser developer console for streaming events

### 4. Run Test Script
```bash
cd backend
uv run python test_streaming.py
```

## Event Flow Example

```
1. User starts investigation
2. ADK agent begins processing
3. Backend receives ADK events:
   - event.partial = true  → 'streaming_text_chunk'
   - event.partial = false → 'complete_text_message' 
   - tool calls            → 'tool_call_request'
   - tool results          → 'tool_result'
4. Events streamed to frontend via SSE
5. Frontend accumulates text chunks
6. UI updates in real-time
```

## Key Benefits

1. **Real-time Feedback**: Users see agent responses as they're generated
2. **Better UX**: No more waiting for complete responses
3. **Transparency**: See tool calls and intermediate steps
4. **Error Handling**: Real-time error display
5. **Performance**: Streaming reduces perceived latency

## Troubleshooting

### No Streaming Events
- Check browser console for SSE connection errors
- Verify backend `/api/investigations/{id}/stream` endpoint is accessible
- Ensure investigation is in RUNNING status

### Partial Text Not Accumulating
- Verify `processStreamingEvent()` is being called
- Check that `streamingTextAccumulator` is properly initialized
- Monitor SSE events in Network tab

### Performance Issues
- Consider limiting streaming text display length
- Add text truncation for very long responses
- Implement cleanup for completed investigations

## Next Steps

1. **Enhanced UI**: Add syntax highlighting for code responses
2. **Tool Visualization**: Visual indicators for tool calls
3. **Streaming Chat**: Extend to chat interface
4. **Error Recovery**: Auto-reconnect on SSE failures
5. **Performance**: Optimize for high-frequency events

This implementation provides a solid foundation for real-time agent interaction in your ADK application!
