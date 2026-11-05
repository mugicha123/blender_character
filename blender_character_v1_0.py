bl_info = {
    "name": "blender_character",
    "author": "User",
    "version": (1, 9, 0),
    "blender": (4, 1, 0),
    "location": "Shader Editor > Sidebar > Shading",
    "description": "Adds a separate anime shader node network without connecting to existing nodes.",
    "category": "Material",
}

import bpy

SHADOW_PROP = "ts_shadow_col_v2"
LIGHT_PROP = "ts_light_col_v2"
SHADOW_POS_PROP = "ts_shadow_pos_v2"
LIGHT_POS_PROP = "ts_light_pos_v2"
TEXTURE_IMAGE_PROP = "ts_texture_image_v2"


class OBJECT_OT_add_anime_shader(bpy.types.Operator):
    bl_idname = "object.add_anime_shader"
    bl_label = "Add Anime Shader"
    bl_description = "Add the anime shader to the material selected in Material Properties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Target the material selected in Material Properties (active material slot).
        obj = context.active_object
        mat = obj.active_material if obj and hasattr(obj, "active_material") else None
        if mat is None:
            mat = getattr(context, "material", None)
        if mat is None:
            self.report({'WARNING'}, "Select a material in Material Properties first.")
            return {'CANCELLED'}

        scene = context.scene
        # Blenderのバージョンに応じて利用可能なEeveeエンジンを選択
        engine_items = scene.render.bl_rna.properties['engine'].enum_items
        available_engines = {item.identifier for item in engine_items}
        if 'BLENDER_EEVEE_NEXT' in available_engines:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        elif 'BLENDER_EEVEE' in available_engines:
            scene.render.engine = 'BLENDER_EEVEE'
        else:
            self.report({'ERROR'}, "Eevee render engine is not available in this Blender version.")
            return {'CANCELLED'}

        shadow_col = tuple(scene.ts_shadow_col_v2)
        light_col = tuple(scene.ts_light_col_v2)

        # Preserve the material's existing nodes and add the anime shader alongside them.
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        # Remember nodes that were selected before generating the anime shader.
        previously_selected_nodes = [node for node in nodes if node.select]

        # Keep the original node network completely untouched and unconnected.
        # Create a separate Material Output for the anime shader network.
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (650, 0)
        output.label = "Anime Shader Output (Separate)"

        # Mix Shader
        mix = nodes.new(type='ShaderNodeMixShader')
        mix.location = (420, 0)
        mix.inputs[0].default_value = 0.7

        # Principled BSDF: base color is driven by the toon ramp
        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (100, 180)
        principled.inputs['Roughness'].default_value = 0.5
        principled.inputs['Metallic'].default_value = 0.01

        # Diffuse BSDF -> Shader to RGB -> Color Ramp
        diffuse = nodes.new(type='ShaderNodeBsdfDiffuse')
        diffuse.location = (-800, -100)

        # Correct Blender node identifier uses RGB (uppercase)
        try:
            shader_to_rgb = nodes.new(type='ShaderNodeShaderToRGB')
        except RuntimeError:
            self.report(
                {'ERROR'},
                "Could not create Shader to RGB. Please use Blender with Eevee support."
            )
            return {'CANCELLED'}
        shader_to_rgb.location = (-570, -100)

        ramp_node = nodes.new(type='ShaderNodeValToRGB')
        ramp_node.location = (-310, -100)
        ramp = ramp_node.color_ramp
        ramp.interpolation = 'LINEAR'
        ramp.elements[0].position = scene.ts_shadow_pos_v2
        ramp.elements[0].color = shadow_col
        ramp.elements[1].position = scene.ts_light_pos_v2
        ramp.elements[1].color = light_col

        # Rampの色をEmissionシェーダーに変換してからMix Shaderへ接続
        emission = nodes.new(type='ShaderNodeEmission')
        emission.location = (120, -160)

        # ノード接続
        links.new(diffuse.outputs['BSDF'], shader_to_rgb.inputs['Shader'])
        links.new(shader_to_rgb.outputs['Color'], ramp_node.inputs['Fac'])
        links.new(ramp_node.outputs['Color'], principled.inputs['Base Color'])
        links.new(ramp_node.outputs['Color'], emission.inputs['Color'])
        links.new(principled.outputs['BSDF'], mix.inputs[1])
        links.new(emission.outputs['Emission'], mix.inputs[2])
        # Connect only the newly-created anime shader nodes to the new output.
        # Do not link to, disconnect, or modify any pre-existing nodes.
        links.new(mix.outputs['Shader'], output.inputs['Surface'])

        # Deselect nodes that were selected before shader generation.
        for node in previously_selected_nodes:
            try:
                node.select = False
            except ReferenceError:
                pass

        self.report({'INFO'}, f"Anime shader added to material: {mat.name}")
        return {'FINISHED'}


class OBJECT_OT_add_anime_shader_textures(bpy.types.Operator):
    bl_idname = "object.add_anime_shader_textures"
    bl_label = "Add Anime Shader"
    bl_description = "Create a separate anime shader network using the selected texture"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        image = getattr(scene, TEXTURE_IMAGE_PROP, None)
        if image is None:
            self.report({'WARNING'}, "Select a texture image first.")
            return {'CANCELLED'}

        obj = context.active_object
        mat = obj.active_material if obj and hasattr(obj, "active_material") else None
        if mat is None:
            mat = getattr(context, "material", None)
        if mat is None:
            self.report({'WARNING'}, "Select a material in Material Properties first.")
            return {'CANCELLED'}

        engine_items = scene.render.bl_rna.properties['engine'].enum_items
        available_engines = {item.identifier for item in engine_items}
        if 'BLENDER_EEVEE_NEXT' in available_engines:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        elif 'BLENDER_EEVEE' in available_engines:
            scene.render.engine = 'BLENDER_EEVEE'
        else:
            self.report({'ERROR'}, "Shader to RGB requires an Eevee render engine.")
            return {'CANCELLED'}

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        previously_selected_nodes = [node for node in nodes if node.select]

        # Add a completely separate network; preserve all existing nodes and links.
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (900, -220)
        output.label = "Texture Anime Shader Output (Separate)"

        mix_shader = nodes.new(type='ShaderNodeMixShader')
        mix_shader.location = (650, -220)
        mix_shader.inputs[0].default_value = 0.700

        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (180, -40)
        principled.inputs['Metallic'].default_value = 0.010
        principled.inputs['Roughness'].default_value = 0.500
        principled.inputs['IOR'].default_value = 1.500
        principled.inputs['Alpha'].default_value = 1.000

        diffuse = nodes.new(type='ShaderNodeBsdfDiffuse')
        diffuse.location = (-1000, -40)
        diffuse.inputs['Roughness'].default_value = 0.000

        try:
            shader_to_rgb = nodes.new(type='ShaderNodeShaderToRGB')
        except RuntimeError:
            self.report({'ERROR'}, "Could not create Shader to RGB. Please use Blender with Eevee support.")
            return {'CANCELLED'}
        shader_to_rgb.location = (-760, -40)

        ramp_node = nodes.new(type='ShaderNodeValToRGB')
        ramp_node.location = (-520, -40)
        ramp = ramp_node.color_ramp
        ramp.interpolation = 'LINEAR'
        ramp.elements[0].position = 0.209
        ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        ramp.elements[1].position = 0.223
        ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)

        image_node = nodes.new(type='ShaderNodeTexImage')
        image_node.location = (-745, -313)
        image_node.image = image

        hsv = nodes.new(type='ShaderNodeHueSaturation')
        hsv.location = (-350, -420)
        hsv.inputs['Hue'].default_value = 0.500
        hsv.inputs['Saturation'].default_value = 1.500
        hsv.inputs['Value'].default_value = 0.250
        hsv.inputs['Fac'].default_value = 1.000

        mix_color = nodes.new(type='ShaderNodeMixRGB')
        mix_color.location = (-100, -120)
        mix_color.label = "Mix Color"

        emission = nodes.new(type='ShaderNodeEmission')
        emission.location = (250, -420)

        links.new(diffuse.outputs['BSDF'], shader_to_rgb.inputs['Shader'])
        links.new(shader_to_rgb.outputs['Color'], ramp_node.inputs['Fac'])
        links.new(image_node.outputs['Color'], hsv.inputs['Color'])
        links.new(hsv.outputs['Color'], mix_color.inputs['Color1'])
        links.new(image_node.outputs['Color'], mix_color.inputs['Color2'])
        links.new(ramp_node.outputs['Color'], mix_color.inputs['Fac'])
        links.new(mix_color.outputs['Color'], principled.inputs['Base Color'])
        links.new(mix_color.outputs['Color'], emission.inputs['Color'])
        links.new(principled.outputs['BSDF'], mix_shader.inputs[1])
        links.new(emission.outputs['Emission'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])

        for node in previously_selected_nodes:
            try:
                node.select = False
            except ReferenceError:
                pass

        self.report({'INFO'}, f"Texture anime shader added to material: {mat.name}")
        return {'FINISHED'}


class VIEW3D_PT_anime_shader_panel(bpy.types.Panel):
    bl_label = "Anime shader for single color"
    bl_idname = "VIEW3D_PT_anime_shader_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Add anime shader"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space is not None and space.type == 'NODE_EDITOR' and space.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Color Settings")
        layout.prop(scene, SHADOW_PROP, text="Shadow Color")
        layout.prop(scene, SHADOW_POS_PROP, text="Shadow Position")
        layout.prop(scene, LIGHT_PROP, text="Light Color")
        layout.prop(scene, LIGHT_POS_PROP, text="Light Position")
        layout.separator()
        layout.operator("object.add_anime_shader", icon='MATERIAL')




class VIEW3D_PT_anime_shader_textures_panel(bpy.types.Panel):
    bl_label = "Anime shader for textures"
    bl_idname = "VIEW3D_PT_anime_shader_textures_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Add anime shader"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space is not None and space.type == 'NODE_EDITOR' and space.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Label and image datablock selector with the same controls as
        # the Image Texture node's image field.
        layout.label(text="Select texture")
        layout.template_ID(scene, TEXTURE_IMAGE_PROP, open="image.open", new="image.new")
        layout.operator("object.add_anime_shader_textures", text="Add anime shader", icon='MATERIAL')


class MESH_OT_apply_character_offset(bpy.types.Operator):
    bl_idname = "mesh.apply_character_offset"
    bl_label = "Apply Character Offset"
    bl_description = "Apply the Offset value to selected mesh geometry using Shrink/Fatten"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH'
            and context.edit_object is not None
            and context.edit_object.type == 'MESH'
        )

    def execute(self, context):
        offset = context.scene.character_object_offset

        # Apply the panel's Offset value as a direct Shrink/Fatten operation.
        # Positive values move selected geometry outward; negative values inward.
        try:
            result = bpy.ops.transform.shrink_fatten(value=offset)
        except Exception as exc:
            self.report({'ERROR'}, f"Could not apply Offset: {exc}")
            return {'CANCELLED'}

        if 'CANCELLED' in result:
            self.report({'WARNING'}, "Shrink/Fatten could not be applied. Check the mesh selection.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Applied Offset: {offset:g} m")
        return {'FINISHED'}


class MESH_OT_create_offset_shrinkwrap_object(bpy.types.Operator):
    bl_idname = "mesh.create_offset_shrinkwrap_object"
    bl_label = "Create an object"
    bl_description = (
        "Duplicate the selected faces, apply Blender Shrink/Fatten using Offset, "
        "and add an unapplied Shrinkwrap modifier targeting the source object"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        source_obj = context.edit_object
        if source_obj is None or source_obj.type != 'MESH':
            self.report({'WARNING'}, "Enter Mesh Edit Mode first.")
            return {'CANCELLED'}

        if context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, "This tool works in Mesh Edit Mode.")
            return {'CANCELLED'}

        import bmesh
        bm = bmesh.from_edit_mesh(source_obj.data)
        selected_faces = [face for face in bm.faces if face.select]
        if not selected_faces:
            self.report({'WARNING'}, "Select one or more faces first.")
            return {'CANCELLED'}

        offset = context.scene.character_object_offset
        objects_before = set(bpy.data.objects)

        try:
            # 1) Duplicate the selected faces and separate the duplicate
            # into a new object. The source mesh remains in place.
            bpy.ops.mesh.duplicate()
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')

            created_objects = [obj for obj in bpy.data.objects if obj not in objects_before]
            if not created_objects:
                self.report({'ERROR'}, "The separated object could not be found.")
                return {'CANCELLED'}

            new_obj = created_objects[-1]

            # Make only the new object active before running the standard
            # Blender Shrink/Fatten transform in Edit Mode.
            bpy.ops.object.select_all(action='DESELECT')
            new_obj.select_set(True)
            context.view_layer.objects.active = new_obj
            bpy.ops.object.mode_set(mode='EDIT')

            # Separate may preserve the selection, but explicitly select all
            # copied faces so the entire new surface receives the Offset.
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.transform.shrink_fatten(value=offset)
            bpy.ops.object.mode_set(mode='OBJECT')

            # Add Shrinkwrap AFTER Shrink/Fatten. Keep it unapplied and
            # target the original body object.
            shrinkwrap = new_obj.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
            shrinkwrap.target = source_obj
            shrinkwrap.offset = offset

        except Exception as exc:
            # Try to leave Blender in Object Mode if an operation failed.
            try:
                if context.object and context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            self.report({'ERROR'}, f"Could not create the offset object: {exc}")
            return {'CANCELLED'}

        # Keep the source body intact and select the newly-created object.
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        self.report(
            {'INFO'},
            f"Created {new_obj.name}; Shrink/Fatten offset: {offset:g} m; "
            "Shrinkwrap added (not applied)."
        )
        return {'FINISHED'}


class VIEW3D_PT_character_object_tool(bpy.types.Panel):
    bl_label = "Create Clothes"
    bl_idname = "VIEW3D_PT_character_object_tool"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.edit_object is not None

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "character_object_offset", text="Offset")
        layout.operator(
            "mesh.create_offset_shrinkwrap_object",
            text="Create Clothes"
        )



# ------------------------------------------------------------------------
# Data Transfer + Armature automation
# ------------------------------------------------------------------------

def _is_mesh_object(self, obj):
    return obj is not None and obj.type == 'MESH'


def _is_armature_object(self, obj):
    return obj is not None and obj.type == 'ARMATURE'


class OBJECT_OT_transfer_vertex_groups_and_add_armature(bpy.types.Operator):
    bl_idname = "object.transfer_vertex_groups_and_add_armature"
    bl_label = "Generate Data Transfer + Armature"
    bl_description = (
        "Transfer vertex groups from the Source mesh, apply Data Transfer, "
        "then add an Armature modifier at the top of the stack"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            context.mode == 'OBJECT'
            and obj is not None
            and obj.type == 'MESH'
        )

    def execute(self, context):
        target = context.active_object
        source_obj = context.scene.character_data_transfer_source
        armature_obj = context.scene.character_data_transfer_armature

        if target is None or target.type != 'MESH':
            self.report({'WARNING'}, "Select the target mesh object first.")
            return {'CANCELLED'}

        if source_obj is None or source_obj.type != 'MESH':
            self.report({'WARNING'}, "指定するSourceにメッシュオブジェクトを設定してください。")
            return {'CANCELLED'}

        if armature_obj is None or armature_obj.type != 'ARMATURE':
            self.report({'WARNING'}, "指定するArmatureにアーマチュアを設定してください。")
            return {'CANCELLED'}

        if source_obj == target:
            self.report({'WARNING'}, "Source and target mesh must be different objects.")
            return {'CANCELLED'}

        # Add and configure Data Transfer on the active target mesh.
        transfer = target.modifiers.new(name="DataTransfer", type='DATA_TRANSFER')
        transfer.object = source_obj
        transfer.mix_mode = 'REPLACE'
        transfer.mix_factor = 1.0
        transfer.use_vert_data = True
        transfer.data_types_verts = {'VGROUP_WEIGHTS'}
        transfer.vert_mapping = 'NEAREST'

        try:
            # Generate the destination vertex-group data layers before transfer.
            result = bpy.ops.object.datalayout_transfer(modifier=transfer.name)
            if 'CANCELLED' in result:
                raise RuntimeError("Generate Data Layers could not be executed.")

            # Apply only the newly-created Data Transfer modifier.
            result = bpy.ops.object.modifier_apply(modifier=transfer.name)
            if 'CANCELLED' in result:
                raise RuntimeError("Data Transfer modifier could not be applied.")

            # Add the Armature modifier and move it to the top of the stack.
            arm_mod = target.modifiers.new(name="Armature", type='ARMATURE')
            arm_mod.object = armature_obj
            arm_mod.use_vertex_groups = True
            arm_mod.use_bone_envelopes = False
            arm_mod.use_deform_preserve_volume = False
            arm_mod.use_multi_modifier = False

            arm_index = list(target.modifiers).index(arm_mod)
            if arm_index != 0:
                target.modifiers.move(arm_index, 0)

        except Exception as exc:
            # If Data Transfer has not yet been applied, remove the temporary modifier.
            remaining = target.modifiers.get(transfer.name)
            if remaining is not None:
                target.modifiers.remove(remaining)
            self.report({'ERROR'}, f"Data Transfer / Armature setup failed: {exc}")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Vertex groups transferred to {target.name}; Armature modifier added."
        )
        return {'FINISHED'}


class VIEW3D_PT_character_data_transfer(bpy.types.Panel):
    bl_label = "Data Transfer + Armature"
    bl_idname = "VIEW3D_PT_character_data_transfer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "character_data_transfer_source", text="Source")
        layout.prop(scene, "character_data_transfer_armature", text="Armature")
        layout.separator()
        layout.operator(
            "object.transfer_vertex_groups_and_add_armature",
            text="Generate",
            icon='MOD_DATA_TRANSFER'
        )



classes = (
    OBJECT_OT_add_anime_shader_textures,
    OBJECT_OT_add_anime_shader,
    VIEW3D_PT_anime_shader_panel,
    VIEW3D_PT_anime_shader_textures_panel,
    MESH_OT_apply_character_offset,
    MESH_OT_create_offset_shrinkwrap_object,
    VIEW3D_PT_character_object_tool,
    OBJECT_OT_transfer_vertex_groups_and_add_armature,
    VIEW3D_PT_character_data_transfer,
)




def unregister():
    # Unregister classes first, then remove Scene properties.
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    for prop in (SHADOW_PROP, LIGHT_PROP, SHADOW_POS_PROP, LIGHT_POS_PROP, TEXTURE_IMAGE_PROP, 'character_object_offset', 'character_data_transfer_source', 'character_data_transfer_armature'):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)


def register():
    # Avoid duplicate registration when re-running the script.
    unregister()

    bpy.types.Scene.character_data_transfer_source = bpy.props.PointerProperty(
        name="Source",
        description="Mesh object used as the source for vertex-group transfer",
        type=bpy.types.Object,
        poll=_is_mesh_object,
    )
    bpy.types.Scene.character_data_transfer_armature = bpy.props.PointerProperty(
        name="Armature",
        description="Armature object used by the new Armature modifier",
        type=bpy.types.Object,
        poll=_is_armature_object,
    )


    bpy.types.Scene.ts_texture_image_v2 = bpy.props.PointerProperty(
        name="Texture Image",
        description="Image used by the texture anime shader",
        type=bpy.types.Image,
    )

    bpy.types.Scene.character_object_offset = bpy.props.FloatProperty(
        name='Offset',
        description='Offset used by Blender Shrink/Fatten when creating the copied surface',
        default=0.0,
        unit='LENGTH',
        precision=4,
    )

    for cls in classes:
        bpy.utils.register_class(cls)


    bpy.types.Scene.ts_shadow_col_v2 = bpy.props.FloatVectorProperty(
        name="Shadow Color",
        subtype='COLOR',
        size=4,
        default=(0.610496, 0.381326, 0.346704, 1.0),
        min=0.0,
        max=1.0,
    )
    bpy.types.Scene.ts_light_col_v2 = bpy.props.FloatVectorProperty(
        name="Light Color",
        subtype='COLOR',
        size=4,
        default=(0.955973, 0.768151, 0.665387, 1.0),
        min=0.0,
        max=1.0,
    )
    bpy.types.Scene.ts_shadow_pos_v2 = bpy.props.FloatProperty(
        name="Shadow Position",
        description="Position of the shadow color stop on the Color Ramp",
        default=0.2,
        min=0.0,
        max=1.0,
        precision=3,
    )
    bpy.types.Scene.ts_light_pos_v2 = bpy.props.FloatProperty(
        name="Light Position",
        description="Position of the light color stop on the Color Ramp",
        default=0.35,
        min=0.0,
        max=1.0,
        precision=3,
    )


if __name__ == "__main__":
    register()