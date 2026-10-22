import matplotlib.pyplot as plt
import numpy as np

# Week 0: Domain bounding box
fig, ax = plt.subplots(figsize=(6, 4))
ax.add_patch(plt.Rectangle((270000, 1415000), 63000, 63000, fill=True, color='lightgreen', alpha=0.5, label='DEM Domain'))
ax.plot(274464, 1438000, 'ro', label='Song Ba Ha Dam')
ax.set_xlim(260000, 340000)
ax.set_ylim(1400000, 1490000)
ax.set_title('Week 0: DEM Domain 18,000 km2')
ax.legend()
plt.savefig('D:\\VTP\\img_week0.png')
plt.close()

# Week 1: V22 Simulation
fig, ax = plt.subplots(figsize=(6, 4))
x = np.linspace(0, 120, 100)
y = 1000 * np.exp(-((x - 60) ** 2) / 400)
ax.plot(x, y, 'b-', linewidth=2, label='Flood Water Level')
ax.fill_between(x, y, color='blue', alpha=0.3)
ax.set_title('Week 1: 120h Flood Simulation')
ax.set_xlabel('Time (hours)')
ax.set_ylabel('Water Level')
plt.savefig('D:\\VTP\\img_week1.png')
plt.close()

# Week 2: GeoTIFF Extraction
fig, ax = plt.subplots(figsize=(6, 4))
Z = np.random.rand(10, 10)
c = ax.imshow(Z, cmap='Blues')
plt.colorbar(c)
ax.set_title('Week 2: Max Depth TIFF Extraction')
plt.savefig('D:\\VTP\\img_week2.png')
plt.close()
