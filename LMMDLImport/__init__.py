bl_info = {  
    "name": "Luigi's Mansion MDL Importer",  
    "author": "PentaChess413",  
    "version": (1, 0),  
    "blender": (5, 0, 0),  
    "location": "File > Import-Export",  
    "description": "Import (and in the future, export) MDLs via subprocess",  
    "category": "Import-Export",  
}  
  
import bpy  
import sys  
import subprocess  
import os  # <-- Add this import  
from bpy_extras.io_utils import ImportHelper, ExportHelper  
  
class ImportMyFormat(bpy.types.Operator, ImportHelper):  
    bl_idname = "import_scene.mdl"  
    bl_label = "Import Luigi's Mansion MDL"  
    filename_ext = ".mdl"  
    filter_glob: bpy.props.StringProperty(default="*.mdl", options={'HIDDEN'})  
  
    def execute(self, context):  
        # Detect platform per-call; avoid class-level code  
        exe = context.preferences.addons[__name__].preferences.mdlconverter_directory
        wrapper = context.preferences.addons[__name__].preferences.collada2gltf_directory
        if sys.platform != "win32":  
            subprocess.run(["wine", exe, self.filepath])
        else:
            subprocess.run([exe, self.filepath])
        subprocess.run([wrapper, f"{os.path.splitext(self.filepath)[0]}/{os.path.splitext(os.path.basename(self.filepath))[0]}.dae"])
        finalpath = f"{os.path.splitext(self.filepath)[0]}/output/{os.path.splitext(os.path.basename(self.filepath))[0]}.gltf"  
        print(finalpath)
        bpy.ops.import_scene.gltf(filepath=finalpath) 
        return {'FINISHED'}  
  
class ExportMyFormat(bpy.types.Operator, ExportHelper):  
    bl_idname = "export_scene.my_format"  
    bl_label = "(NOT IMPLEMENTED: IT WILL FAIL!!!) Export Luigi's Mansion MDL"  
    filename_ext = ".mdl"  
    filter_glob: bpy.props.StringProperty(default="*.mdl", options={'HIDDEN'})  
  
    def execute(self, context):  
        temp_blend = bpy.data.filepath or "temp_export.blend"  
        bpy.ops.wm.save_mainfile(filepath=temp_blend, copy=True)  
        subprocess.run(["myfmt_exporter", "--input", temp_blend, "--output", self.filepath])  
        return {'FINISHED'}  
  
class MyAddonPreferences(bpy.types.AddonPreferences):  
    bl_idname = __name__  
  
    has_run_before: bpy.props.BoolProperty(  
        name="Has Run Before",  
        description="Internal flag to detect first run",  
        default=False,  
    )  
  
    collada2gltf_directory: bpy.props.StringProperty(  
        name="COLLADA2Gltf converter",  
        description="Required because Blender does not support COLLADA anymore",  
        default="",  
        subtype='FILE_PATH'
    )  

    mdlconverter_directory: bpy.props.StringProperty(
        name="MdlConverter",
        description="The actual program that does the conversion",
        default="",
        subtype='FILE_PATH'
    )
  
    def draw(self, context):  
        layout = self.layout  
        layout.prop(self, "collada2gltf_directory")
        layout.prop(self, "mdlconverter_directory")  
  
class WM_OT_first_run_prompt(bpy.types.Operator):  
    """Popup shown on first run"""  
    bl_idname = "wm.first_run_prompt"  
    bl_label = "First Run"  
    bl_options = {'INTERNAL'} 
    collada2gltf: bpy.props.StringProperty(name="Collada2GLTF executable", subtype="FILE_PATH")
    modelconverter: bpy.props.StringProperty(name="MdlConverter executable", subtype="FILE_PATH")
  
    def execute(self, context):  
        prefs = context.preferences.addons[__name__].preferences  
        prefs.has_run_before = True
        prefs.collada2gltf_directory = self.collada2gltf
        prefs.mdlconverter_directory = self.modelconverter
        return {'FINISHED'}  
  
    def invoke(self, context, _event):  
        wm = context.window_manager  
        return wm.invoke_props_dialog(self)  
  
    def draw(self, context):  
        layout = self.layout  
        layout.label(text="Welcome to My Format add-on!")
        layout.prop(self, "collada2gltf")  
        layout.prop(self, "modelconverter")
  
def show_first_run_prompt():  
    prefs = bpy.context.preferences.addons[__name__].preferences  
    if not prefs.has_run_before:  
        bpy.ops.wm.first_run_prompt('INVOKE_DEFAULT')  
  
def menu_func_import(self, context):  
    self.layout.operator(ImportMyFormat.bl_idname, text="Luigi's Mansion MDL (.mdl)")  
  
def menu_func_export(self, context):  
    self.layout.operator(ExportMyFormat.bl_idname, text="My Format (.myfmt)")  
  
classes = (  
    ImportMyFormat,  
    ExportMyFormat,  
    MyAddonPreferences,  
    WM_OT_first_run_prompt,  
)  
  
def register():  
    for cls in classes:  
        bpy.utils.register_class(cls)  
    bpy.app.timers.register(show_first_run_prompt, first_interval=0.1)  
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)  
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)  
  
def unregister():  
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)  
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.app.timers.unregister(show_first_run_prompt)  
    for cls in reversed(classes):  
        bpy.utils.unregister_class(cls)  
  
if __name__ == "__main__":  
    register()