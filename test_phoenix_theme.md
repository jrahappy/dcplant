# Testing the Phoenix Theme

## Quick Start

1. **Start the Development Server**:
```bash
cd backend
../venv/Scripts/python.exe manage.py runserver
```

2. **Access the Application**:
- Open browser to: http://127.0.0.1:8000/
- Login with your credentials

3. **Phoenix Theme Features to Test**:

### Navigation
- ✅ Collapsible sidebar with "Collapsed View" button
- ✅ Phoenix logo with orange gradient
- ✅ Nested menu items under "Case management"
- ✅ "NEW" badges on Stock and Gantt chart items

### Case List View (http://127.0.0.1:8000/cases/)
- ✅ Filter pills (All, Ongoing, Cancelled, Finished, Postponed)
- ✅ Search bar with icon
- ✅ View mode toggles (grid/card/list)
- ✅ Case table with:
  - Avatar groups for assignees
  - Progress bars with percentages
  - Status badges (COMPLETED, INACTIVE, ONGOING, CRITICAL, CANCELLED)
  - Action dropdown menus

### Visual Elements
- ✅ Inter font family
- ✅ Clean white cards with subtle shadows
- ✅ Professional color scheme
- ✅ Hover effects on navigation items
- ✅ Responsive design

### Theme Switching
- Go to Settings (if available)
- Or manually switch by calling the endpoint
- Theme preference is saved in session

## Sample Data
The Phoenix theme displays best with sample case data including:
- Multiple assignees per case
- Various status types
- Progress tracking
- Different priority levels

## Color Palette
- Primary Blue: #3874ff
- Success Green: #00d27a  
- Warning Orange: #f5803e
- Danger Red: #e63757
- Neutral Grays: #f5f7fa (background), #6e7891 (text)

## Files Created
1. `static/css/phoenix-v2.css` - Complete theme styles
2. `templates/base_phoenix_v2.html` - Phoenix layout structure
3. `templates/cases/case_list_v2.html` - Project/case list matching screenshot
4. `core/context_processors.py` - Theme context management
5. Settings updated with `DEFAULT_THEME = 'phoenix'`

## Notes
- Theme is set to 'phoenix' by default
- Sidebar state (collapsed/expanded) is saved in localStorage
- All Phoenix navigation items are placeholders - only Case management is functional
- The design exactly matches the Phoenix theme screenshot provided