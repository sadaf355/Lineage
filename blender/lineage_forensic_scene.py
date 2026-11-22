import bpy

# Optional Blender helper for the LINEAGE forensic-network hero asset.
# Run inside Blender 4.x, then export the selected collection as GLB.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for i, loc in enumerate([(0,0,0),(-2,1,0),(2,1,0),(-1.6,-1.2,0),(1.6,-1.2,0)]):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=.34 if i==0 else .18, location=loc)
    obj=bpy.context.object
    obj.name=f'LINEAGE_Node_{i+1}'
    mat=bpy.data.materials.new(f'LINEAGE_Mat_{i+1}')
    mat.diffuse_color=(0.12,0.7,0.42,1)
    mat.metallic=.45
    mat.roughness=.25
    obj.data.materials.append(mat)
print('Created LINEAGE forensic nodes. Export the collection as GLB.')
