# KK/VRC Cloth Tools

这套工具用于把 VRC 服装迁移到 Koikatsu/KK 骨架流程中，当前包含两个部分：

- Blender 插件：`kk_vrc_cloth_tools`，负责接骨、权重重映射、风险区域混合、贴身衣物权重传递、拓扑导出。
- Unity Editor 脚本：`UnityBoneImplant.cs`，负责给导入 Unity 后的服装对象自动添加 `BoneImplantProcess`，并可选添加 `DynamicBone`。

假设你是从 GitHub Release 下载：

- Blender 插件压缩包，例如 `kk_vrc_cloth_tools.zip`
- Unity 脚本文件 `UnityBoneImplant.cs`

## Blender 插件安装

要求：

- Blender 4.3 或以上
- 已在 Blender 中准备好 KK Armature、VRC/服装 Armature 或已经接好的服装 mesh

安装方式：

1. 打开 Blender。
2. 进入 `Edit > Preferences > Add-ons`。
3. 点击右上角下拉菜单或 `Install from Disk...`。
4. 选择 Release 里的 `kk_vrc_cloth_tools.zip`。
5. 启用插件 `KK/VRC Cloth Tools`。
6. 在 3D View 中按 `N` 打开侧边栏，进入 `KK/VRC Tools` 标签页。

如果 Blender 界面语言是中文，插件会自动使用中文界面文本。

## Blender 使用流程

推荐按插件面板中的顺序执行。每一步都建议先点 `Preview` 或 `Scan Preview`，确认 Console 报告没有明显异常后再 `Apply`。

### Step 1 - Graft Clothes Physical Bones To KK

用途：把服装自带的物理骨接到 KK Armature 上。

基本用法：

1. 选中 KK Armature 和 VRC/服装 Armature。
2. 在面板里选择接骨模式，默认推荐 `Waist`。
3. 点击 `Scan Preview` 检查将要接入的骨骼 root。
4. 点击 `Apply` 执行。

注意：

- `Pelvis / Waist / High Waist` 会影响未知服装 root 接到 KK 身体哪一段。
- 一般衣裙、腰部装饰优先尝试 `Waist`。
- 胸部、腰腹、臀部这类风险区域不要只依赖一对一主骨映射，后续步骤会单独处理。

### Step 2 - Remap Low-Risk Body Groups

用途：把低风险 VRC 主骨顶点组改名到 KK 主骨。

它会处理头颈、手臂、腿、手指、脚趾等区域；不会处理：

- `Hips`
- `Spine`
- `Chest`
- `Butt.L`
- `Butt.R`

这些被排除的区域请用 Step 3 处理。

### Step 3 - Mix Torso / Hip / Butt Weights

用途：处理躯干、腰腹、臀部权重，减少下躯干、腰线、臀部布料穿模。

模式：

- `Balanced`：默认推荐，分布到 `hips / waist01 / waist02 / spine / siri` 等 KK 骨骼。
- `Conservative`：更保守，目标骨更少，适合 Balanced 过软或拉伸明显时对比。

可选项：

- `Remove source groups after apply`：应用后删除原 VRC 源组，默认建议开启。
- `Normalize affected vertices only`：只归一化受影响顶点，默认建议开启。
- 平滑选项：用于让刚分配过的风险区域和周边顶点过渡更自然。

### Step 4A - Breast Simple Remap

用途：把 `Breast_root / Breast_1 / Breast_2` 简单映射到 KK 胸部链。

模式：

- `Simple J Chain`：一对一映射，清晰直接。
- `Distributed J Chain`：把单个 VRC 胸骨权重分配到相邻 KK 胸骨，过渡更柔和。

适合贴身胸部布料、胸衣、上衣胸前布料。

### Step 4B - Breast Local Mix

用途：在胸部区域保留一部分身体权重，同时把胸部物理权重转入 KK bust bones。

常用默认：

- `Distributed J Chain`
- `Breast influence = 0.70`
- `Body influence = 0.30`

如果胸部边缘出现硬折痕，优先尝试 4B，而不是 4A。

### Step 5 - Transfer KK Body Weights To Fitted Clothes

用途：直接从 KK 身体 mesh 把权重传给贴身衣物。

适合：

- 内衣
- 紧身衣
- 袜子
- 手套
- 贴身上衣或裤袜

不适合：

- 裙摆
- 飘带
- 披风
- 已经主要靠服装物理骨控制的区域

基本用法：

1. 在 `Source body mesh` 指定 KK 身体 mesh。
2. 选中要接收权重的服装 mesh。
3. 先 `Preview`，确认受影响顶点数量。
4. 再 `Apply`。

`Physical weight threshold` 用于保护物理骨区域。值越低，越不会覆盖服装物理骨控制的顶点。

### Utilities - Export Armature Topology JSON

用途：导出当前选中 Armature 的骨骼拓扑 JSON，用于检查骨骼层级、标准骨列表或后续脚本维护。

## Unity 脚本安装

要求：

- Unity 项目已导入 Koikatsu/KK mod 制作用到的工具。
- 项目中能找到 `BoneImplantProcess` 类型。
- 如果要自动添加动态骨，还需要项目中已有 `DynamicBone`。

安装方式：

1. 在 Unity 项目中创建或找到 `Assets/Editor` 文件夹。
2. 把 Release 里的 `UnityBoneImplant.cs` 放进 `Assets/Editor`。
3. 等 Unity 编译完成。
4. 菜单栏打开 `Tools > KK Mods > Auto Bone Implant`。

## Unity 使用流程

1. 把从 Blender 导出的 FBX 导入 Unity。
2. 将导入后的服装 prefab 或场景中的服装最顶级对象拖到 `Root Object`。
3. 点击 `Scan Preview`。
4. 检查 Preview 列表，确认类似：

```text
服装物理骨Root -> KK父骨
```

5. 点击 `Apply Preview`。

脚本会把 `BoneImplantProcess` 组件添加到 `Root Object` 上，而不是添加到每根骨骼上。每个组件会记录：

- `trfSrc`：服装自定义骨 root
- `trfDst`：它应该接到的 KK 标准父骨

## Unity Dynamic Bone 选项

如果需要同时添加 `DynamicBone`，勾选：

```text
Add/Update Dynamic Bone components after implant
```

绑定模式：

- `ImplantRoots`：Dynamic Bone 的 Root 直接使用 implant root。
- `FirstLevelChildren`：Dynamic Bone 的 Root 使用 implant root 的下一级子骨。

常见选择：

- 如果一整条物理链从 root 开始摆动，选 `ImplantRoots`。
- 如果 root 只是挂点，真正摆动从下一节开始，选 `FirstLevelChildren`。

`Skip existing Dynamic Bone roots` 建议开启，避免重复添加同一个 Root。

## 导出和导入注意事项

- Blender 导出 FBX 前，确认服装 mesh 的 Armature modifier 指向最终 KK Armature。
- Unity 中看到 FBX 根对象 X 轴旋转 90 度通常是 Blender/Unity 坐标系转换导致；只要 prefab 内部骨骼、mesh 和动画/绑定关系正常，一般不影响使用。
- 对贴身衣物，优先考虑 Step 5 权重传递。
- 对裙摆、飘带、蝴蝶结等动态结构，优先保留服装物理骨，并在 Unity 中添加 `BoneImplantProcess` 和 `DynamicBone`。
- 每次大改权重前建议保留一份 Blender 备份文件，方便对比不同模式。

## 推荐完整流程

1. Blender：导入/准备 KK 模型和 VRC 服装。
2. Blender Step 1：接入服装物理骨。
3. Blender Step 2：迁移低风险主骨权重。
4. Blender Step 3：处理躯干、腰腹、臀部。
5. Blender Step 4A 或 4B：处理胸部。
6. Blender Step 5：对贴身衣物做 KK 身体权重传递。
7. Blender：导出 FBX。
8. Unity：导入 FBX。
9. Unity：使用 `Auto Bone Implant` 添加 `BoneImplantProcess`。
10. Unity：按需要添加 `DynamicBone`。

## 排错

- Blender 插件没有显示：确认已启用插件，并在 3D View 按 `N` 打开 `KK/VRC Tools`。
- `Preview` 没有对象：确认选中了 mesh 或 Armature，mesh 的 Armature modifier 指向正确骨架。
- Unity 找不到 `BoneImplantProcess`：确认 KoikatsuModdingTools / ModBoneImplantor 已导入项目。
- Unity 找不到 `DynamicBone`：如果项目没有 Dynamic Bone，关闭自动添加 Dynamic Bone 选项。
- Preview 结果太少：关闭 prefix filter，或确认服装物理骨确实被 SkinnedMeshRenderer 使用。
- Preview 结果太多：开启 prefix filter，或检查是否有非服装骨被误命名为自定义骨。
