import bpy


def is_armature(obj):
    return obj is not None and obj.type == "ARMATURE"


def is_mesh(obj):
    return obj is not None and obj.type == "MESH"


def set_status(context, message):
    props = getattr(context.scene, "kkvrc_cloth_tools", None)
    if props is not None:
        props.last_status = message


def get_active_kk_armature(context=None):
    context = context or bpy.context
    obj = context.view_layer.objects.active
    if is_armature(obj):
        return obj

    for selected in context.selected_objects:
        if is_armature(selected):
            return selected

    for selected in context.selected_objects:
        if not is_mesh(selected):
            continue
        for modifier in selected.modifiers:
            if modifier.type == "ARMATURE" and is_armature(modifier.object):
                return modifier.object

    raise RuntimeError("Select the KK Armature, make it active, or select a mesh whose Armature modifier points to it.")


def get_selected_armatures(context=None):
    context = context or bpy.context
    kk_armature = context.view_layer.objects.active
    if not is_armature(kk_armature):
        raise RuntimeError("Make the KK target Armature the active object.")

    selected = [obj for obj in context.selected_objects if is_armature(obj)]
    if len(selected) != 2:
        raise RuntimeError("Select exactly two Armatures: active = KK target, other selected = VRC source.")

    vrc_armatures = [obj for obj in selected if obj != kk_armature]
    if len(vrc_armatures) != 1:
        raise RuntimeError("Could not identify the VRC source Armature.")

    return kk_armature, vrc_armatures[0]


def is_descendant_of(obj, parent):
    current = obj.parent
    while current:
        if current == parent:
            return True
        current = current.parent
    return False


def get_target_meshes(kk_armature, context=None):
    context = context or bpy.context
    selected_meshes = [obj for obj in context.selected_objects if is_mesh(obj)]
    if selected_meshes:
        return selected_meshes

    meshes = [obj for obj in bpy.data.objects if is_mesh(obj) and is_descendant_of(obj, kk_armature)]
    if not meshes:
        raise RuntimeError("No selected meshes and no mesh children found under the KK Armature.")

    return meshes


def get_armature_bone_names(armature_obj):
    return {bone.name for bone in armature_obj.data.bones}


def get_or_create_group(obj, name):
    group = obj.vertex_groups.get(name)
    if group is None:
        group = obj.vertex_groups.new(name=name)
    return group


def get_vertex_weight(vertex, group_index):
    for group in vertex.groups:
        if group.group == group_index:
            return group.weight
    return 0.0


def set_weight(obj, group_name, vertex_index, weight):
    group = get_or_create_group(obj, group_name)
    if weight <= 0.0:
        try:
            group.remove([vertex_index])
        except RuntimeError:
            pass
    else:
        group.add([vertex_index], weight, "REPLACE")


def remove_vertex_from_group(group, vertex_index):
    try:
        group.remove([vertex_index])
    except RuntimeError:
        pass


def normalize_affected_vertices(obj, vertex_indices):
    for vertex_index in vertex_indices:
        vertex = obj.data.vertices[vertex_index]
        total = sum(group.weight for group in vertex.groups if group.weight > 0.0)
        if total <= 0.0:
            continue
        for group_ref in list(vertex.groups):
            vertex_group = obj.vertex_groups[group_ref.group]
            vertex_group.add([vertex_index], group_ref.weight / total, "REPLACE")


def build_vertex_adjacency(obj):
    adjacency = [set() for _vertex in obj.data.vertices]
    for edge in obj.data.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)
    return adjacency


def expand_vertex_region(obj, vertex_indices, rings):
    region = set(vertex_indices)
    if rings <= 0 or not region:
        return region

    adjacency = build_vertex_adjacency(obj)
    frontier = set(region)
    for _index in range(rings):
        next_frontier = set()
        for vertex_index in frontier:
            next_frontier.update(adjacency[vertex_index])
        next_frontier.difference_update(region)
        if not next_frontier:
            break
        region.update(next_frontier)
        frontier = next_frontier
    return region


def smooth_vertex_group_weights(obj, seed_indices, group_names, iterations=2, strength=0.35, expand_rings=1, normalize=True):
    group_names = [name for name in dict.fromkeys(group_names) if obj.vertex_groups.get(name) is not None]
    if not seed_indices or not group_names or iterations <= 0 or strength <= 0.0:
        return 0

    strength = max(0.0, min(1.0, strength))
    region = expand_vertex_region(obj, seed_indices, expand_rings)
    if not region:
        return 0

    adjacency = build_vertex_adjacency(obj)

    for _iteration in range(iterations):
        snapshot = {}
        sample_vertices = set(region)
        for vertex_index in region:
            sample_vertices.update(adjacency[vertex_index])

        for vertex_index in sample_vertices:
            vertex = obj.data.vertices[vertex_index]
            snapshot[vertex_index] = {
                group_name: get_vertex_weight(vertex, obj.vertex_groups[group_name].index)
                for group_name in group_names
            }

        updates = []
        for vertex_index in region:
            neighbors = adjacency[vertex_index]
            if not neighbors:
                continue
            for group_name in group_names:
                current = snapshot[vertex_index][group_name]
                average = sum(snapshot[neighbor][group_name] for neighbor in neighbors) / len(neighbors)
                updates.append((vertex_index, group_name, current + (average - current) * strength))

        for vertex_index, group_name, weight in updates:
            set_weight(obj, group_name, vertex_index, weight)

    if normalize:
        normalize_affected_vertices(obj, region)

    return len(region)


def normalize_vertex_subset(obj, vertex_index, group_names):
    vertex = obj.data.vertices[vertex_index]
    total = 0.0
    for group_name in group_names:
        group = obj.vertex_groups.get(group_name)
        if group is not None:
            total += get_vertex_weight(vertex, group.index)
    if total <= 0.0:
        return
    for group_name in group_names:
        group = obj.vertex_groups.get(group_name)
        if group is None:
            continue
        weight = get_vertex_weight(vertex, group.index)
        if weight > 0.0:
            group.add([vertex_index], weight / total, "REPLACE")


def remove_empty_groups(obj, names):
    for name in names:
        group = obj.vertex_groups.get(name)
        if group is None:
            continue
        has_weights = any(get_vertex_weight(vertex, group.index) > 0.0 for vertex in obj.data.vertices)
        if not has_weights:
            obj.vertex_groups.remove(group)


def group_has_weights(obj, group_index):
    for vertex in obj.data.vertices:
        for group in vertex.groups:
            if group.group == group_index and group.weight > 0.0:
                return True
    return False


def get_selection_status(context=None):
    context = context or bpy.context
    active = context.view_layer.objects.active
    selected_armatures = [obj for obj in context.selected_objects if is_armature(obj)]
    selected_meshes = [obj for obj in context.selected_objects if is_mesh(obj)]
    kk_name = active.name if is_armature(active) else "(active is not Armature)"
    vrc_names = [obj.name for obj in selected_armatures if obj != active]
    return kk_name, ", ".join(vrc_names) if vrc_names else "(none)", len(selected_meshes)


def print_report(title, reports, sections):
    print("\n" + title)
    print("=" * len(title))
    if not reports:
        print("(none)")
        return
    for report in reports:
        print(f"\nMesh: {report.get('mesh', '(none)')}")
        if "affected_vertices" in report:
            print(f"  Affected vertices: {report['affected_vertices']}")
        for key, label in sections:
            values = report.get(key)
            if values:
                if isinstance(values, (list, tuple, set)):
                    print(f"  {label}: {', '.join(str(item) for item in values)}")
                else:
                    print(f"  {label}: {values}")
