# Selection Tree Component

A reusable Django template component that provides an interactive tree-based selection interface using jsTree. Users can browse and select items from a hierarchical structure.

## Overview

The Selection Tree component displays a collapsible tree structure where users can navigate through parent nodes and select leaf nodes. When a leaf node is selected, it dispatches a custom event that can be listened to by other parts of your application.

## Usage

### Basic Implementation

Include the component in your Django template:

```django
{% include "components/selection_tree/selection_tree.html" with selection_type="Email Template" selection_tree_data=folder_tree %}

// Make sure this loads after the entire page loads
document.addEventListener('DOMContentLoaded', function() {
// Load template content when template is selected
    document.addEventListener('treeSelectionChanged', function(event) {
        // event.detail.node.li_attr contains HTML list element attributes
        someLogic(event)
    });
});
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `selection_type` | string | Yes | The label describing what type of items are being selected (e.g., "Email Template", "Folder", "Category") |
| `selection_tree_data` | list | Yes | A list of dictionaries representing the tree structure (see Data Format below) |

## Data Format

The `selection_tree_data` parameter expects a list of dictionaries with the following structure:

```python
[
    {
        "node_name": str,        # Display name for the parent node
        "node_value": int/str,   # Optional: value for parent node
        "children": [            # List of child nodes (leaf nodes)
            {
                "node_name": str,      # Display name for the leaf node
                "node_value": int/str, # Value returned when selected
            },
            # ... more leaf nodes
        ]
    },
    # ... more parent nodes
]
```

### Example Data Structure

```python
folder_tree = [
    {
        "node_name": "Marketing Templates",
        "node_value": 1,
        "children": [
            {
                "node_name": "Welcome Email",
                "node_value": 101,
            },
            {
                "node_name": "Newsletter",
                "node_value": 102,
            }
        ]
    },
    {
        "node_name": "System Templates",
        "node_value": 2,
        "children": [
            {
                "node_name": "Password Reset",
                "node_value": 201,
            }
        ]
    }
]
```

## Events

### `treeSelectionChanged`

Dispatched when a user selects a leaf node. Listen for this event to handle selections:

```javascript
document.addEventListener('treeSelectionChanged', function(event) {
    const selectionData = event.detail;
    // selectionData.node contains the selected node information
    // selectionData.node.li_attr.value contains the node_value
    console.log('Selected:', selectionData.node);
});
```

## Dependencies

### External Libraries

- **jsTree 3.2.1** - Tree view library
  - CSS: `https://cdnjs.cloudflare.com/ajax/libs/jstree/3.2.1/themes/default/style.min.css`
  - JS: `https://cdnjs.cloudflare.com/ajax/libs/jstree/3.2.1/jstree.min.js`
- **jQuery** - Required by jsTree (must be loaded before this component)

### Bootstrap

The component uses Bootstrap classes for styling and collapse functionality:
- `collapse`
- `btn`, `btn-outline-secondary`, `btn-sm`
- `form-label`
- `mb-3`, `mt-2`, `ml-2`

## Behavior

1. **Parent Nodes**: Clicking a parent node expands/collapses it (does not trigger selection)
2. **Leaf Nodes**: Clicking a leaf node:
   - Dispatches the `treeSelectionChanged` event
   - Automatically closes the collapsible container
   - Updates the button's `aria-expanded` attribute

## Customization

### Changing the Selection Type Label

Modify the `selection_type` parameter:

```django
{% include "components/selection_tree/selection_tree.html" with selection_type="Your Custom Label" selection_tree_data=your_data %}
```

### Custom Styling

Override CSS classes or add custom styles by targeting:
- `#jstree_container` - Main tree container
- `#jstreeCollapse` - Collapsible wrapper
- `.btn[data-target="#jstreeCollapse"]` - Toggle button

## Example: Full Integration

```django
<!-- In your Django template -->
{% include "components/selection_tree/selection_tree.html" with selection_type="Email Template" selection_tree_data=folder_tree %}

<script>
document.addEventListener('treeSelectionChanged', function(event) {
    const selectedValue = event.detail.node.li_attr.value;
    const selectedName = event.detail.node.text;
    
    // Update a hidden input field
    document.getElementById('selected_template_id').value = selectedValue;
    
    // Update UI
    document.getElementById('selected_template_name').textContent = selectedName;
    
    // Make API call or form submission
    // ...
});
</script>

<input type="hidden" id="selected_template_id" name="template_id" value="">
<span id="selected_template_name"></span>
```

## Notes

- Only leaf nodes (items with `data-node-type="leaf"`) trigger the selection event
- Parent nodes are for navigation only
- The component automatically handles tree expansion/collapse
- The collapsible container closes automatically after selection

