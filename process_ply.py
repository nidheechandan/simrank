import numpy as np
import json
import os

input_ply = r"c:\Users\shaya\Desktop\ROOM NEW\COLMAP_PREP\colmap-room-static\dense-pod2-hq\fused-room-hq.ply"
output_dir = r"c:\Users\shaya\Desktop\Projects\simrank-room-scan"

def parse_ply(filepath):
    with open(filepath, 'rb') as f:
        header = []
        while True:
            line = f.readline().decode('ascii', errors='ignore').strip()
            header.append(line)
            if line == 'end_header':
                break
        
        num_vertices = 0
        properties = []
        is_binary = False
        
        for line in header:
            if line.startswith('format'):
                if 'binary' in line:
                    is_binary = True
            elif line.startswith('element vertex'):
                num_vertices = int(line.split()[-1])
            elif line.startswith('property'):
                parts = line.split()
                if len(parts) >= 3:
                    prop_type = parts[1]
                    prop_name = parts[2]
                    properties.append((prop_name, prop_type))
                
        # Handle properties mapping
        dtype_map = {
            'float': 'f4', 'float32': 'f4', 
            'double': 'f8', 'float64': 'f8',
            'uchar': 'u1', 'uint8': 'u1',
            'char': 'i1', 'int8': 'i1',
            'ushort': 'u2', 'uint16': 'u2',
            'short': 'i2', 'int16': 'i2',
            'uint': 'u4', 'uint32': 'u4',
            'int': 'i4', 'int32': 'i4'
        }
        
        dt_list = []
        for name, ptype in properties:
            if ptype in dtype_map:
                dt_list.append((name, dtype_map[ptype]))
            else:
                print(f"Warning: Unknown property type {ptype}")
        
        dt = np.dtype(dt_list)
        
        if is_binary:
            data = np.fromfile(f, dtype=dt, count=num_vertices)
        else:
            data = np.loadtxt(f, dtype=dt)
            
        return data

print("Reading PLY file...")
data = parse_ply(input_ply)

# Try different property names just in case
x = data['x']
y = data['y']
z = data['z']

try:
    r = data['red']
    g = data['green']
    b = data['blue']
except ValueError:
    r = data['diffuse_red']
    g = data['diffuse_green']
    b = data['diffuse_blue']

positions = np.vstack((x, y, z)).T
colors = np.vstack((r, g, b)).T

print(f"Original point count: {len(positions)}")

# Trim outliers (within 3 standard deviations of median in each axis)
medians = np.median(positions, axis=0)
stds = np.std(positions, axis=0)
print(f"Medians: {medians}, Stds: {stds}")

mask = np.all(np.abs(positions - medians) <= 3 * stds, axis=1)
positions = positions[mask]
colors = colors[mask]

print(f"Trimmed point count: {len(positions)}")

# Export binary float32 positions
pos_path = os.path.join(output_dir, 'cloud_positions.json')
with open(pos_path, 'wb') as f:
    f.write(positions.astype(np.float32).tobytes())
    
# Export uint8 RGB colors
col_path = os.path.join(output_dir, 'cloud_colors.json')
with open(col_path, 'wb') as f:
    f.write(colors.astype(np.uint8).tobytes())

# Bounding box and meta
min_bounds = np.min(positions, axis=0)
max_bounds = np.max(positions, axis=0)
center = (min_bounds + max_bounds) / 2
radius = np.linalg.norm(max_bounds - center)
bbox_dim = max_bounds - min_bounds

meta = {
    "n": len(positions),
    "center": center.tolist(),
    "radius": float(radius)
}

with open(os.path.join(output_dir, 'meta.json'), 'w') as f:
    json.dump(meta, f)

anchors = [
    [-1.74, -1.16, 0.32],
    [1.74, -1.16, 0.32],
    [0.00, 1.74, 0.32],
    [-1.74, 4.64, 0.32],
    [1.74, 4.64, 0.32],
    [0.00, 7.54, 0.32],
    [0.00, 8.70, 0.32]
]

with open(os.path.join(output_dir, 'anchors.json'), 'w') as f:
    json.dump(anchors, f)

print(f"Final point count: {len(positions)}")
print(f"Positions file size: {os.path.getsize(pos_path)}")
print(f"Colors file size: {os.path.getsize(col_path)}")
print(f"Bounding box dimensions: {bbox_dim}")
