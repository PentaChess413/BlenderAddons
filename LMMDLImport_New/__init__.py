# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
try:
    from construct import *
except ImportError:
    import subprocess
    import sys
    subprocess.check_call(subprocess.check_call([sys.executable, "-m", "pip", "install", "construct"]))
from .mdl import *
import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper, StringProperty
import bmesh
from math import *
import mathutils

bl_info = {
    "name": "ADDON_NAME",
    "author": "AUTHOR_NAME",
    "description": "",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}


class MyImporter(bpy.types.Operator, ImportHelper):  
    """Load a custom file"""  
    bl_idname = "import_scene.mdl"  
    bl_label = "Import Luigi's Mansion Actor Model"  
    bl_options = {'REGISTER', 'UNDO'}  
      
    filename_ext = ".mdl"  
    filter_glob: StringProperty(default="*.mdl", options={'HIDDEN'})  
    def execute(self, context):  
            mdldata = MDL.parse_file(self.filepath)  
            textures = mdldata.textures  
            bis = []
            tex_index = 0  
            for texture in textures:  
                print(texture)
                width = int(texture.width)  
                height = int(texture.height)  
          
                img = bpy.data.images.new(f"Tex_{tex_index}", width, height, alpha=True)  
          
                texdata = texture.texdata  
          
                img.pixels = decode_texture(texdata, texture.width, texture.height, int(texture.format))  
                bis.append(img)
                tex_index += 1
            materials = mdldata.materials
            bmaterials = []
            mat_index = 0
            for material in materials:  
                print(material)  
                mat = bpy.data.materials.new(name=f"Material_{mat_index}")  
                mat.use_nodes = True  
                mat.node_tree.nodes.clear()  
      
                output_node = mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')  
                principled_node = mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')  
      
                mat.node_tree.links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])  
      
                principled_node.inputs["Base Color"].default_value = [  
                    material.diffuse_color.r,   
                    material.diffuse_color.g,   
                    material.diffuse_color.b,   
                    material.diffuse_color.a  
                ]  
      
                if len(material.tev_stages) > 0 and material.tev_stages[0].sampler_index != 65535:  
                    samp = mdldata.samplers[material.tev_stages[0].sampler_index]  
                    tex = textures[samp.texture_index]  
          
                    tex_node = mat.node_tree.nodes.new(type='ShaderNodeTexImage')  
                    tex_node.image = bis[samp.texture_index] 
                    print(tex_node.image) 
          
                    if samp.wrap_mode_u == samp.wrap_mode_v:  
                        if samp.wrap_mode_u == 'REPEAT':  
                            tex_node.extension = 'REPEAT'  
                        elif samp.wrap_mode_u == 'CLAMPTOEDGE':  
                            samp.extension = 'EXTEND'  
                        elif samp.wrap_mode_u == 'MIRROR':  
                            tex_node.extension = 'MIRROR'  
                    else:  
                        tex_node.extension = 'REPEAT'  
          
                    mat.node_tree.links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])  
                bmaterials.append(mat)
                mat_index += 1
            btransforms = []
            armature = bpy.data.armatures.new("LM_Armature")
            armature_obj = bpy.data.objects.new(f"ArmatureObject", armature)  
            bpy.context.collection.objects.link(armature_obj)  
            bpy.context.view_layer.objects.active = armature_obj    
            arm_index = 0 
            
            for i in range(0, mdldata.header.joint_count*11, 11):
                matrix4 = [
                    [mdldata.matrices[i], mdldata.matrices[i + 1], mdldata.matrices[i + 2], mdldata.matrices[i + 3]],
                    [mdldata.matrices[i + 4], mdldata.matrices[i + 5], mdldata.matrices[i + 6], mdldata.matrices[i + 7]],
                    [mdldata.matrices[i + 8], mdldata.matrices[i + 9], mdldata.matrices[i + 10], mdldata.matrices[i + 11]],
                    [0, 0, 0, 1]
                ]
                matrix4 = invert4(matrix4)
                matrix4 = transpose(matrix4)
                btransforms.append(matrix4)
  
                bpy.ops.object.mode_set(mode='EDIT')
                trans, rot, scale = decompose_matrix(matrix4)
                print(trans)
                print(rot)
                print(scale)
                bone_name = f"Mesh_{i//11}" if mdldata.nodes[i//11].draw_element_count > 0 else f"Bone_{i//11}"
                bone = armature.edit_bones.new(bone_name)
                bone.head = trans
                scale_magnitude = sqrt(scale[0]**2 + scale[1]**2 + scale[2]**2)
                trans_vec = mathutils.Vector((trans))
                bone.tail = trans_vec + mathutils.Vector((0, 1, 0)) * scale_magnitude
                rot_mat = mathutils.Matrix(rot)
                bone.align_roll(rot_mat @ mathutils.Vector((0, 1, 0)))
                arm_index += 1
            traverse_node_graph(mdldata, armature, 0)
            armature_obj.scale = (3.0, 3.0, 3.0)
            mesh_index = 0
            for i in range(mdldata.header.draw_element_count):
                mesh = bpy.data.meshes.new(name=f"Mesh_{mesh_index}")
                mesh_obj = bpy.data.objects.new(f"MeshObj_{mesh_index}", mesh)
                bpy.context.collection.objects.link(mesh_obj)
                mat = bmaterials[mdldata.draw_elements[mesh_index].material_index]
                mesh_obj.data.materials.append(mat)
                packets = []
                for i1 in range(mdldata.shapes[mdldata.draw_elements[mesh_index].shape_index].packet_count):
                    packet = mdldata.packets[mdldata.shapes[mdldata.draw_elements[mesh_index].shape_index].packet_begin_index + i1]
                    packets.append(packet)
                    verts = []
                    for v in range(packet.data.vertex_count):
                        vertex = packet.data.vertices[v]
                        if vertex.matrix_index != -1 and vertex.matrix_data_index < mdldata.header.joint_count:
                            matrix = btransforms[vertex.matrix_data_index]
                        else:
                            matrix = [
                                [1, 0, 0, 0],
                                [0, 1, 0, 0],
                                [0, 0, 1, 0],
                                [0, 0, 0, 1]
                            ]
                        position = [mdldata.positions[vertex.position_index].x, mdldata.positions[vertex.position_index].y, mdldata.positions[vertex.position_index].z, 1]
                        normal = [0, 0, 0, 0]
                        texcoord = [0, 0]
                        color = [1, 1, 1, 1]
                        bone_indices = []
                        bone_weights = []
                        if vertex.normal_index:
                            normal[0], normal[1], normal[2] = mdldata.normals[vertex.normal_index].x, mdldata.normals[vertex.normal_index].y, mdldata.normals[vertex.normal_index].z
                        if vertex.texcoord_index:
                            texcoord[0], texcoord[1] = mdldata.texcoords[vertex.texcoord_index].x, mdldata.texcoords[vertex.texcoord_index].y
                        if vertex.color_index:
                            color[0], color[1], color[2], color[3] = mdldata.colors[vertex.color_index].r, mdldata.colors[vertex.color_index].g, mdldata.colors[vertex.color_index].b, mdldata.colors[vertex.color_index].a
                        if vertex.matrix_data_index >= mdldata.header.joint_count:
                            weight_index = vertex.matrix_data_index - mdldata.header.joint_count
                            weights = mdldata.weight_values[weight_index]
                            for i2, j in enumerate(mdldata.joint_indices):
                                bone_indices.append(mdldata.joint_indices[i2])
                                bone_weights.append(weights)
                        elif vertex.matrix_index != -1:
                            bone_indices.append(vertex.matrix_data_index)
                            bone_weights.append(1)
                        
                        position = [sum(matrix[i2][j] * position[j] for j in range(4)) for i2 in range(4)]
                        normal = [sum(matrix[i2][j] * position[j] for j in range(4)) for i2 in range(3)]
                        verts.append([position, normal, bone_indices, bone_weights, texcoord, color])
                    bm = bmesh.new()
                    bm.from_mesh(mesh)
                    deform_layer = bm.verts.layers.deform.verify()
                    match packet.data.opcode:
                        case Opcode.GX_TRIANGLE:
                            vertex_index = 0
                            for v in range(packet.data.vertex_count):
                                for w in range(3):
                                    v1, v2, v3 = bm.verts.new((verts[vertex_index][0][0], verts[vertex_index][0][1], verts[vertex_index][0][2])), bm.verts.new((verts[vertex_index + 1][0][0], verts[vertex_index + 1][0][1], verts[vertex_index + 1][0][2])), bm.verts.new((verts[vertex_index + 2][0][0], verts[vertex_index + 2][0][1], verts[vertex_index + 2][0][2]))
                                    v1.normal, v2.normal, v3.normal = (verts[vertex_index][1][0], verts[vertex_index][1][1], verts[vertex_index][1][2]), (verts[vertex_index + 1][1][0], verts[vertex_index + 1][1][1], verts[vertex_index + 1][1][2]), (verts[vertex_index + 2][1][0], verts[vertex_index + 2][1][1], verts[vertex_index + 2][1][2])
                                    face = bm.faces.new([v1, v2, v3])
                                    for loop in v1.link_loops:
                                        loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = verts[vertex_index][4][0], verts[vertex_index][4][1]
                                    for loop in v2.link_loops:
                                        loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = verts[vertex_index + 1][4][0], verts[vertex_index + 1][4][1]
                                    for loop in v3.link_loops:
                                        loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = verts[vertex_index + 2][4][0], verts[vertex_index + 2][4][1]
                                    dv1, dv2, dv3 = v1[deform_layer], v2[deform_layer], v3[deform_layer]
                                    for idx, weight in zip(verts[vertex_index][2], verts[vertex_index][3]):
                                        dv1[idx] = weight
                                    for idx, weight in zip(verts[vertex_index + 1][2], verts[vertex_index + 1][3]):
                                        dv2[idx] = weight
                                    for idx, weight in zip(verts[vertex_index + 2][2], verts[vertex_index + 2][3]):
                                        dv3[idx] = weight
                                    vertex_index += 3
                            print(bm.verts.length)
                            bm.to_mesh(mesh)
                            bm.free()
                        case Opcode.GX_TRIANGLESTRIP:
                            for v in range(packet.data.vertex_count):
                                tristrip_verts = []
                                for i2 in range(2, packet.data.vertex_count):
                                    is_even = i2 % 2 != 1
                                    v1 = verts[i2 - 2]
                                    v2 = verts[i2] if is_even else verts[i2 - 1]
                                    v3 = verts[i2 - 1] if is_even else verts[i2]
                                    if v1[0] != v2[0] and v2[0] != v3[0] and v3[0] != v1[0]:
                                        tristrip_verts.append(v2)
                                        tristrip_verts.append(v3)
                                        tristrip_verts.append(v1)
                                        bv1 = bm.verts.new((v1[0][0], v1[0][1], v1[0][2]))
                                        bv2 = bm.verts.new((v2[0][0], v2[0][1], v2[0][2]))
                                        bv3 = bm.verts.new((v3[0][0], v3[0][1], v3[0][2]))
                                        bv1.normal, bv2.normal, bv3.normal = (v1[1][0], v1[1][1], v1[1][2]), (v2[1][0], v2[1][1], v2[1][2]), (v3[1][0], v3[1][1], v3[1][2])
                                        for loop in bv1.link_loops:
                                            loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = v1[4][0], v1[4][1]
                                        for loop in bv2.link_loops:
                                            loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = v2[4][0], v2[4][1]
                                        for loop in bv3.link_loops:
                                            loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = v3[4][0], v3[4][1]
                                        bm.faces.new([bv1, bv2, bv3])
                                        dv1, dv2, dv3 = bv1[deform_layer], bv2[deform_layer], bv3[deform_layer]
                                        for idx, weight in zip(verts[i - 2][2], verts[i - 2][3]):
                                            dv1[idx] = weight
                                        for idx, weight in zip(verts[i if is_even else i - 1][2], verts[i if is_even else i - 1][3]):
                                            dv2[idx] = weight
                                        for idx, weight in zip(verts[i - 1 if is_even else i][2], verts[i - 1 if is_even else i][3]):
                                            dv3[idx] = weight
                                print(tristrip_verts)
                        case Opcode.GX_TRIANGLEFAN:
                            vertex_id = verts[0]
                            trifan_verts = []
                            first_vert = vertex_id
                            for i2 in range(3):
                                trifan_verts.append(verts[i2])
                            for i2 in range(2, packet.data.vertex_count):
                                v1, v2, v3 = first_vert, verts[i2 - 1], verts[i2]
                                if v1[0] != v2[0] and v2[0] != v3[0] and v3[0] != v1[0]:
                                    trifan_verts.append(v2)
                                    trifan_verts.append(v3)
                                    trifan_verts.append(v1)
                                    bv1 = bm.verts.new((v1[0][0], v1[0][1], v1[0][2]))
                                    bv2 = bm.verts.new((v2[0][0], v2[0][1], v2[0][2]))
                                    bv3 = bm.verts.new((v3[0][0], v3[0][1], v3[0][2]))
                                    bm.faces.new([bv1, bv2, bv3])
                                    for loop in bv1.link_loops:
                                        loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = v1[4][0], v1[4][1]
                                    for loop in bv2.link_loops:
                                        loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = v2[4][0], v2[4][1]
                                    for loop in bv3.link_loops:
                                        loop[bm.loops.layers.uv.verify()].uv.x, loop[bm.loops.layers.uv.verify()].uv.y = v3[4][0], v3[4][1]
                                    dv1, dv2, dv3 = bv1[deform_layer], bv2[deform_layer], bv3[deform_layer]
                                    for idx, weight in zip(first_vert[2], first_vert[3]):
                                        dv1[idx] = weight
                                    for idx, weight in zip(verts[i2 - 1][2], verts[i2 - 1][3]):
                                        dv2[idx] = weight
                                    for idx, weight in zip(verts[i2][2], verts[i2][3]):
                                        dv3[idx] = weight
                            print(bm.verts)
                    
                    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

                    seen_faces = set()
                    for f in bm.faces:
                        verts = tuple(sorted([v.index for v in f.verts]))
                        if verts not in seen_faces:
                            seen_faces.add(verts)
                        else:
                            bmesh.ops.delete(bm, geom=[f], context='FACES_ONLY')
                    
                    bm.to_mesh(mesh)
                    bm.free()
                    for i2 in range(mdldata.header.joint_count):
                        bone_name = f"Mesh_{i2}" if mdldata.nodes[i2].draw_element_count > 0 else f"Bone_{i}"
                        mesh_obj.vertex_groups.new(name=bone_name)
                    
                    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
                    mod.object = armature_obj
                mesh_index += 1
            return {'FINISHED'}
            
  
class MyExporter(bpy.types.Operator, ExportHelper):  
    """Save a custom file"""  
    bl_idname = "export_scene.mdl"  
    bl_label = "Export Luigi's Mansion Actor Model"  
      
    filename_ext = ".mdl"  
    filter_glob: StringProperty(default="*.mdl", options={'HIDDEN'})  
      
    def execute(self, context): 
        ''' 
        textures = [tex for tex in bpy.data.textures]

        sorted_textures = sorted(textures, key=lambda tex: int(tex.name.split('_')[1]))

        bones = bpy.data.armatures['LM_Armature'].bones
        builttextures = []
        builtsamplers = []
        for texture in sorted_textures:
            rawdata = [0] * (texture.size[0] * texture.size[1] * 4)
            texture.pixels.foreacj_get(rawdata)
            texdata = '',join(f'\\x{int(p * 255):02x}' for p in rawdata)
            tex = dict(format=TextureFormats.CMPR, width=texture.size[0], height=texture.size[1], texdata=encode_cmpr(texdata, texture.size[0], texture.size[1]))
            builttexture = Texture.build(tex)
            builttextures.append(builttexture)
            samp = dict(wrap_mode_u=WrapMode.MIRROR, wrap_mode_v=WrapMode.MIRROR, mag_filter=0, min_filter=0, tex_index=textures.index(texture))
            builtsampler = Sampler.build(samp)
            builtsamplers.append(builtsampler)
            '''
        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(MyImporter.bl_idname, text="Luigi's Mansion Actor Model (.mdl)")
    
def menu_func_export(self, context):
    self.layout.operator(MyExporter.bl_idname, text="Luigi's Mansion Actor Model (.mdl)")

def register(): 
    bpy.utils.register_class(MyImporter)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(MyExporter)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(MyImporter)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(MyExporter)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)