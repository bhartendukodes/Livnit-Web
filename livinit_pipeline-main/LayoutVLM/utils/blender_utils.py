import argparse
import sys
import os
import math
import re
import bpy
import bmesh
from bpy_extras.image_utils import load_image
import numpy as np
from scipy.signal import correlate2d
from scipy.ndimage import shift
import json
from mathutils import Vector

def setup_background():
    """Sets up a white background world shader."""
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    
    # Clear existing nodes
    nodes = world.node_tree.nodes
    nodes.clear()
    
    # Create the nodes for the world shader
    output_node = nodes.new(type='ShaderNodeOutputWorld')
    output_node.location = (200, 0)
    background_node = nodes.new(type='ShaderNodeBackground')
    background_node.location = (0, 0)
    
    # Set background node to emit white light
    background_node.inputs['Color'].default_value = (1, 1, 1, 1)  # White
    background_node.inputs['Strength'].default_value = 1.0
    
    # Connect the nodes
    world.node_tree.links.new(background_node.outputs['Background'], output_node.inputs['Surface'])

def reset_blender():
    """Completely resets the Blender scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Clean up any lingering data blocks that read_factory might miss in module mode
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)
    
    # Create default collection if needed
    if "Collection" not in bpy.data.collections:
        bpy.ops.collection.create(name="Collection")
        bpy.context.scene.collection.children.link(bpy.data.collections["Collection"])
    
    # Purge orphans to free memory
    bpy.ops.outliner.orphans_purge(do_recursive=True)

def clear_render_results():
    """Removes render result images to free memory."""
    for image in bpy.data.images:
        if image.type == 'RENDER_RESULT':
            bpy.data.images.remove(image)

def reset_scene():
    """Clears objects, materials, and textures from the current scene."""
    # Unlink all objects first
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    # Check for users and remove materials
    for material in bpy.data.materials:
        if material.users == 0:
            bpy.data.materials.remove(material, do_unlink=True)

    # Check for users and remove textures
    for texture in bpy.data.textures:
        if texture.users == 0:
            bpy.data.textures.remove(texture, do_unlink=True)

    # Check for users and remove images
    for image in bpy.data.images:
        if image.users == 0:
            bpy.data.images.remove(image, do_unlink=True)

def import_glb(file_path, location=(0, 0, 0), rotation=(0, 0, 0), scale=(0.01, 0.01, 0.01), centering=True):
    """Imports a GLB file and handles parenting/scaling/location."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
    
    # Capture selected objects before import to identify new ones
    bpy.ops.object.select_all(action='DESELECT')
    
    try:
        bpy.ops.import_scene.gltf(filepath=file_path)
    except RuntimeError as e:
        print(f"Error importing GLB: {e}")
        return None

    selected_objects = bpy.context.selected_objects
    if not selected_objects:
        return None
        
    # If multiple objects imported, try to find the root parent
    imported_object = selected_objects[0]
    roots = [o for o in selected_objects if o.parent is None]
    if roots:
        imported_object = roots[0]

    # Apply transformations
    imported_object.rotation_euler = rotation
    imported_object.scale = scale

    if centering:
        # Save current active object
        prev_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = imported_object
        
        # Origin to geometry center
        bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN', center='BOUNDS')
        
    imported_object.location = location
    return imported_object

def create_wall_mesh(name, vertices):
    """Creates a wall mesh from a list of vertices."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)

    scene = bpy.context.scene
    scene.collection.objects.link(obj)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Build mesh using BMesh
    bm = bmesh.new()
    for v in vertices:
        # Ensure 3D coordinates
        if len(v) == 2:
            bm.verts.new((v[0], v[1], 0.0))
        else:
            bm.verts.new(v)
            
    bm.verts.ensure_lookup_table()

    # Create edges (assuming ordered vertices forming a perimeter)
    if len(vertices) > 1:
        for i in range(len(vertices)-1):
            bm.edges.new([bm.verts[i], bm.verts[i+1]])
        
        # Close the loop
        if len(vertices) > 2:
            try:
                bm.edges.new([bm.verts[-1], bm.verts[0]])
                bm.faces.new(bm.verts)
            except ValueError:
                pass # Edge might already exist

    bm.to_mesh(mesh)
    bm.free()
    return obj 

def create_cube(name, min_xyz, max_xyz, location, rotate=False):
    """Creates a cube (often used for debugging bounds)."""
    dimensions = [max_xyz[i] - min_xyz[i] for i in range(3)]
    
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    cube = bpy.context.active_object
    cube.dimensions = dimensions

    if rotate:
        bpy.context.view_layer.objects.active = cube
        bpy.ops.transform.rotate(value=math.radians(90), orient_axis='Z')

    cube.name = name
    return cube

def is_image_loaded(image_filepath):
    for image in bpy.data.images:
        if image.filepath == image_filepath:
            return image
    return None

def apply_texture_to_object(obj, texture_path):
    if not os.path.exists(texture_path):
        return

    mat = bpy.data.materials.new(name="TextureMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")

    tex_image = mat.node_tree.nodes.new('ShaderNodeTexImage')
    try:
        tex_image.image = bpy.data.images.load(texture_path)
    except RuntimeError:
        print(f"Failed to load texture: {texture_path}")
        return

    mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

def add_material(obj, path_texture, add_uv=False, material_pos=-1, texture_scale=(1.8, 1.8), existing_material_name=None):
    material_id = os.path.basename(path_texture)
    
    if add_uv:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project()
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.context.view_layer.objects.active = obj

    existing_material = bpy.data.materials.get(material_id)
    if existing_material:
        new_material = existing_material
    else:
        new_material = bpy.data.materials.new(name=material_id)
        new_material.use_nodes = True
        node_tree = new_material.node_tree

        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

        principled_node = node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        image_texture_node = node_tree.nodes.new(type='ShaderNodeTexImage')
        
        resolutions = ["1K", "2K", "12K"]
        found_res = None
        for resolution in resolutions:
            if os.path.exists(f"{path_texture}/{material_id}_{resolution}-JPG_Color.jpg"):
                found_res = resolution
                break
        
        if not found_res:
            # Fallback or exit
            return

        img_path = f"{path_texture}/{material_id}_{found_res}-JPG_Color.jpg"
        image = is_image_loaded(img_path)
        if image is None:
            image = load_image(img_path)
        image_texture_node.image = image

        tex_coord_node = node_tree.nodes.new(type='ShaderNodeTexCoord')
        mapping_node = node_tree.nodes.new(type='ShaderNodeMapping')
        mapping_node.inputs['Scale'].default_value[0] = texture_scale[0]
        mapping_node.inputs['Scale'].default_value[1] = texture_scale[1]

        node_tree.links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
        node_tree.links.new(mapping_node.outputs['Vector'], image_texture_node.inputs['Vector'])
        node_tree.links.new(image_texture_node.outputs["Color"], principled_node.inputs["Base Color"])
        
        material_output_node = node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        node_tree.links.new(principled_node.outputs["BSDF"], material_output_node.inputs["Surface"])

    if existing_material_name is not None:
        for slot in obj.material_slots:
            if slot.material and existing_material_name.lower() in slot.material.name.lower():
                obj.data.materials.append(new_material)
                new_slot_index = len(obj.material_slots) - 1
                for polygon in obj.data.polygons:
                    if polygon.material_index == obj.material_slots.find(slot.name):
                        polygon.material_index = new_slot_index
    else:
        if material_pos == -1 or len(obj.data.materials) == 0:
            obj.data.materials.clear()
            obj.data.materials.append(new_material)
        else:
            obj.data.materials[material_pos] = new_material

def load_hdri(hdri_path='./data/HDRIs/studio_small_08_4k.exr', hdri_strength=1, hide=True):
    # Resolve relative path if needed
    if not os.path.exists(hdri_path):
        current_file = os.path.abspath(__file__)
        hdri_path = os.path.join(os.path.dirname(os.path.dirname(current_file)), hdri_path)

    world = bpy.data.worlds.get('World')
    if not world: 
        world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
    
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    env_texture = nodes.new(type='ShaderNodeTexEnvironment')
    texture_coord = nodes.new(type="ShaderNodeTexCoord")
    mapping_node = nodes.new(type='ShaderNodeMapping')

    if os.path.exists(hdri_path):
        try:
            env_texture.image = bpy.data.images.load(hdri_path)
        except RuntimeError:
            print(f"Warning: Could not load HDRI image at {hdri_path}")

    background = nodes.new(type='ShaderNodeBackground')
    background.location = (-100, 0)
    
    world_output = nodes.new(type='ShaderNodeOutputWorld')
    world_output.location = (100, 0)

    if hide:
        light_path = nodes.new(type='ShaderNodeLightPath')
        mix_shader = nodes.new(type='ShaderNodeMixShader')
        bg_transparent = nodes.new(type='ShaderNodeBackground')
        bg_transparent.inputs['Color'].default_value = (0, 0, 0, 1)
        
        links.new(light_path.outputs['Is Camera Ray'], mix_shader.inputs['Fac'])
        links.new(background.outputs['Background'], mix_shader.inputs[1])
        links.new(bg_transparent.outputs['Background'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'], world_output.inputs['Surface'])
    else:
        links.new(background.outputs['Background'], world_output.inputs['Surface'])

    links.new(texture_coord.outputs['Generated'], mapping_node.inputs['Vector'])
    links.new(mapping_node.outputs['Vector'], env_texture.inputs['Vector'])
    links.new(env_texture.outputs['Color'], background.inputs['Color'])
    background.inputs['Strength'].default_value = hdri_strength

def setup_camera(center_x, center_y, width, wall_height=.1, wide_lens=False, fov_multiplier=1.1, use_damped_track=False):
    if "Camera" not in bpy.data.objects:
        bpy.ops.object.camera_add()
        cam = bpy.context.object
    else:
        cam = bpy.data.objects["Camera"]
    
    bpy.context.scene.camera = cam
    
    if cam.data is None:
        cam.data = bpy.data.cameras.new("Camera")

    if wide_lens:
        cam.data.lens = 18

    # Safe defaults to avoid div by zero
    lens = cam.data.lens if cam.data.lens > 0 else 50
    sensor_width = cam.data.sensor_width if cam.data.sensor_width > 0 else 36
    
    target_width = abs(fov_multiplier * width)
    fov = 2 * math.atan((sensor_width / (2 * lens)))
    
    cam.location.x = center_x
    cam.location.y = center_y
    # Calculate Z height to cover the target width
    if math.tan(fov / 2) != 0:
        cam.location.z = wall_height + (target_width / 2) / math.tan(fov / 2)
    else:
        cam.location.z = 10.0 # Fallback

    cam.constraints.clear()
    
    empty_name = "CameraTarget"
    if empty_name in bpy.data.objects:
        empty = bpy.data.objects[empty_name]
    else:
        empty = bpy.data.objects.new(empty_name, None)
        bpy.context.scene.collection.objects.link(empty)
    
    empty.location = (center_x, center_y, 0)

    if use_damped_track:
        const = cam.constraints.new(type="DAMPED_TRACK")
        const.track_axis = "TRACK_NEGATIVE_Z"
        const.target = empty
    else:
        const = cam.constraints.new(type="TRACK_TO")
        const.track_axis = "TRACK_NEGATIVE_Z"
        const.up_axis = "UP_Y"
        const.target = empty

    return cam, const

def world_to_camera_view(scene, camera, coord):
    """Wrapper for bpy_extras.object_utils.world_to_camera_view"""
    from bpy_extras.object_utils import world_to_camera_view as w2cv
    return w2cv(scene, camera, coord)

def get_pixel_coordinates(scene, camera, world_coord):
    """Get pixel coordinates (0-1, 0-1) for a given world coordinate."""
    if isinstance(world_coord, (list, tuple)):
        world_coord = Vector(world_coord)
    elif isinstance(world_coord, np.ndarray):
        world_coord = Vector(world_coord.tolist())

    coord_2d = world_to_camera_view(scene, camera, world_coord)
    
    # Return normalized coordinates (x, 1-y) 
    # Blender origin is bottom-left, image origin usually top-left
    return (coord_2d.x, 1.0 - coord_2d.y)

def set_rendering_settings(panorama=False, high_res=False):
    scene = bpy.context.scene
    render = scene.render
    
    # --- CRITICAL FIX FOR DOCKER/HEADLESS ---
    # Check environment variable to decide engine
    engine_env = os.environ.get("BLENDER_RENDER_ENGINE", "BLENDER_EEVEE_NEXT")
    
    if engine_env == "CYCLES":
        render.engine = 'CYCLES'
        # Configure Cycles for CPU rendering in Docker
        scene.cycles.device = os.environ.get("CYCLES_DEVICE", "CPU")
        scene.cycles.samples = 64  # Lower samples for faster headless render
        scene.cycles.use_denoising = True
    else:
        # Fallback for Eevee (might crash in docker without GPU)
        try:
            # Blender 4.2+ uses BLENDER_EEVEE_NEXT
            render.engine = 'BLENDER_EEVEE_NEXT'
        except:
            # Older Blender uses BLENDER_EEVEE
            render.engine = 'BLENDER_EEVEE'

    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = "RGBA"
    
    if high_res:
        render.resolution_x = 1024
        render.resolution_y = 1024
    else:
        render.resolution_x = 512
        render.resolution_y = 512
    
    render.resolution_percentage = 100
    render.film_transparent = True

def display_vertex_color():
    bpy.ops.object.mode_set(mode='OBJECT')
    obj = bpy.context.active_object
    if not obj: return

    material = bpy.data.materials.new(name="ColorAttributeMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()

    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    output = nodes.new(type='ShaderNodeOutputMaterial')
    material.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    if obj.data.attributes:
        # Try to find a color attribute
        col_attr = None
        for attr in obj.data.attributes:
            if attr.domain in {'POINT', 'CORNER'} and attr.data_type in {'FLOAT_COLOR', 'BYTE_COLOR'}:
                col_attr = attr.name
                break
        
        if col_attr:
            attr_node = nodes.new(type='ShaderNodeAttribute')
            attr_node.attribute_name = col_attr
            material.node_tree.links.new(attr_node.outputs['Color'], bsdf.inputs['Base Color'])

    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Renders given obj file.')
    parser.add_argument('--output', type=str, default='./temp_rendering/', help='Output path.')
    # Add dummy args to prevent failure if called with extra params
    parser.add_argument('--json', help='json path')
    parser.add_argument('--content', help='content path')
    parser.add_argument('--asset_source', help='asset source')
    parser.add_argument('--asset_dir', help='asset dir')
    
    # When running inside Blender, sys.argv includes blender flags. 
    # Use known_args to ignore them if needed, or filter sys.argv.
    if "--" in sys.argv:
        args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    else:
        # Fallback if running purely as python script (though bpy needs blender context)
        try:
            args = parser.parse_args()
        except:
            pass