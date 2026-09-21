# MMD → KK：骨骼数据与适配调研

调研日期：2026-09-20。对照 Codex 会话“权重 进阶”及本地最新源码（含动作优化、源辅助骨保留、actual_source 校验）。本轮只读检查 Blender，新增研究数据；未修改原模型、权重、姿势或插件运行入口。

## 结论与数据定位

六类逐顶点预算、可选手指保留、按权重特征选择初值、动作优化与局部精调的总体结构可以用于 MMD。**用户明确规定：正式入口是已转成 T pose、删除适当占位骨并完成清理的模型，不是原生 MMD 导入场景。** 若处理后已满足现有通用蒙皮/采样要求，主要扩展是 MMD 骨名识别、身体角色及语义映射，不必为原生 MMD 约束系统另写完整求值器。

下文的 70 个约束、追加变换和 A pose 等，是当前原始样本的预处理检查项，不是最终输入必然存在的算法障碍。只有预处理后仍保留的特殊求值行为，才需要额外动作采样适配。

MMD 有广泛沿用的标准/准标准骨骼约定，但没有能覆盖任意模型、且可直接把集合外全部认定为衣物动骨的强制白名单。PMX 骨骼记录包含自由命名、父索引、追加变换与 IK 等信息。准标准骨又增加捩骨、D 链、肩抵消等结构。[MMD Tools PMX 实现](https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/pmx/__init__.py)、[准标准骨插件文档](https://nanoem.readthedocs.io/ja/latest/plugin.html)。

VRC 的 Humanoid 是语义槽位要求，同样不强制原骨骼的具体名字；本项目 VRC 数据本来也是模型配置，不能作为所有 VRC 模型的完备白名单。[VRChat 骨架文档](https://creators.vrchat.com/avatars/rig-requirements/)

新增文件：

- `Armature_armature_topology_MMD_R4_Liv.json`：沿用既有 `armature_topology_v1` 格式，完整记录当前样本 423 根骨骼的父子关系、静止矩阵及头尾位置。坐标只属于本模型。
- `bone_profiles/mmd_conventions_v1.json`：候选语义表，区分常用身体骨、身体辅助骨、手指、控制、面部及本样本扩展。`observed_r4_liv_extension` 不是 MMD 通用规范。
- `bone_profiles/mmd_r4_liv_v1.json`：模型实例的识别结果、实际正权重统计、追加变换、约束和同根模型内的刚体证据。包含可提取的 `body_candidate_names`。

两个 profile 的状态均为 `RESEARCH_NOT_RUNTIME_CONFIG`。`candidate_kind`、`budget_region_hint`、`reference_semantic_hint` 不是已审核的 `roles`、`body_map` 或 `bone_map`。当前插件没有加载这些 JSON 的入口；本轮没有宣称 MMD 运行时已实现，也没有改动另一会话的算法代码。

实例 profile 标记为 `RAW_IMPORTED_REFERENCE`，用于预处理前对照；清理完成后应重新导出 `PREPROCESSED_T_POSE` 实例，不能用本轮的骨骼数量、父链和约束统计代替最终数据。

## 正式入口：预处理后的 T pose 模型

流程改为：原始 MMD → T pose 与清理 → 重新审计和源快照 → MMD 语义映射 → 既有权重流程。

- 用户认可的预处理结果是迁移与优化的源基准。原生 MMD 的全部控制/物理运行时行为不是本阶段必须重建的目标；本轮也不自动执行这些预处理操作。
- T pose 要使衣物、骨架静止矩阵和后续参考姿势一致；仅在 Pose Mode 摆成 T pose，而流程随后又重置 matrix_basis 回到旧 A pose，不算满足入口。可在独立处理副本中落实静止姿势，保留原始文件。
- 占位骨不是按名字或无权重一律删除。确认不承重且不再被父链、追加变换、约束或需要保留的动骨引用后，才可直接删除。承担控制作用但不加权的骨，需先解除/转换相应依赖。
- 有实际权重的捩骨、D 骨、身体辅助骨应保留为身体变形骨，或在预处理时显式完成经确认的等价转换与权重映射。不能将其误作占位骨删除后仅靠归一化补足。
- 原始到清理后的重命名、删除、合并及父链变更保留映射记录。正式 BODY/DYNAMIC 分类、六类预算、手指配置和动作参考均从**清理后**的源模型重新建立；不要求原始权重原封不动跨越用户认可的预处理。
- 原衣物与待迁移副本的顶点/拓扑对应，应在预处理完成后建立；以后若再细分、删点或改拓扑，需更新对应。不能把预处理前的顶点编号直接用于预处理后的模型。
- 最终入口核对现有 `_rig` 要求：正确绑定的单一 Armature 修改器、普通 LBS、无未支持的约束/驱动/活动形态键等；并在代表性动作下验证数值蒙皮与 Blender 求值一致。若满足这些要求，直接复用已有导出器；未满足时针对残留项处理，不自动判定需要实现完整 MMD 运行时。

## 识别边界

| 骨骼类别 | 预算/处理建议 |
|---|---|
| 下半身、上半身及脊柱扩展、首、頭 | TORSO；头颈沿用项目约定 |
| 左右肩、腕、ひじ、手首、腕捩/手捩及各自付与辅助骨 | 同侧 ARM；每根加权辅助骨保留自身实际变形矩阵 |
| 左右足、ひざ、足首，以及足D、ひざD、足首D、足先EX | 同侧 LEG；D 链是身体变形链，不是衣物动骨 |
| 左右手指 | 仍标识为所属 ARM，启用的指别单独保留份额；不可向非手指区域引入手指影响 |
| 全ての親、センター、グルーブ、IK、肩P/C、抵消骨 | 控制/依赖，不因无权重就从源动作链删除；意外有权重时 REVIEW |
| 导入器的 dummy/shadow | 依据导入器元数据识别依赖；不能仅靠下划线前缀判断 |
| 自定义骨、身体柔性骨、衣物骨、发饰等 | 核对所属网格与用途；未知默认 REVIEW |

优先保留 Blender 实名与 `mmd_bone.name_j`，记录别名，不重命名原骨。识别层可以用 NFKC 兼容全角数字/IK，并支持 `.L/.R`，但必须检查归一化碰撞和名字与元数据冲突；不能合并原权重，不能去掉 `.001` 后盲目匹配。MMD 工具本身可能区分全角与半角，这只是我们的识别规则。

刚体证据必须限定到当前 MMD root。PMX 的 mode 0 是骨骼跟随碰撞体，不能据此判断为衣物动骨；mode 1/2 也只能支持 PHYSICS_CANDIDATE，因为乳房、头发和衣物都可能带物理。此场景未 Build Physics，Blender rigid_body.type 显示 ACTIVE 不能替代 MMD mode 语义。是否嫁接、是否保留源变形、预算归属和是否驱动物理是四件不同的事。

## 当前 R4丽芙 样本的实际结果

源文件 `D:/Program/liv/liv origin.blend`；骨架 `R4丽芙_arm`，MMD root `R4丽芙`；Blender 5.2.0 LTS，MMD Tools 4.5.14。

| 项目 | 实测 |
|---|---:|
| 骨骼 / 绑定资产网格 | 423 / 12 |
| 有正权重的真实骨骼 | 286 |
| 候选身体及辅助骨（有权重） | 38 |
| 手指骨（有权重） | 30 |
| 带物理证据的候选骨（有权重，尚未审核用途） | 180 |
| 其余待审核骨（有权重） | 38 |
| 骨骼约束 / 未静音且 influence > 0 的约束 | 70 / 66 |
| 声明追加旋转/位移的骨骼 | 32 |
| 同 root 刚体（mode 0 / 1 / 2） | 227（42 / 181 / 4） |
| 排除的其他 root 或无归属刚体 | 77 |

正权重统计覆盖全部 12 个绑定网格，包含手套、头发等，不等于本次衣物任务应保留的骨数。`mmd_edge_scale`、`mmd_vertex_order` 是正值顶点组，但不是骨骼，不能纳入权重分母。

1. 腿部 FK `足.L/R → ひざ.L/R → 足首.L/R` 没有直接网格权重；D 链有权重，并从对应 FK 骨追加旋转。因此 motion controls 可以选 FK，source deformation 必须取 D 骨求值结果，不能把这两类映射混为一谈。
2. 腕捩、手捩及 1/2/3 辅助骨有实际权重；本例付与系数为 0.25/0.5/0.75。肩C 还使用 -1 的追加旋转。不能把辅助权重删掉后归一化，也不能假设它们在所有动作中等同于父骨。
3. 躯干顺序为 `腰 → 上半身 → 上半身3 → 上半身2 → 首 → 頭`，而 `下半身` 是 `腰` 的另一分支。不可按数字顺序或单个 Hips 映射硬套 KK 脊柱链。
4. `胸上2.L/R` 有身体部位语义及 mode 1 刚体，暂列物理候选而非已批准的衣物 DYNAMIC。`WingsBone*`、`TieBone*` 等有权重但未找到同 root 的直接刚体关联；不能仅因名字非标准就自动判断衣物动骨。
5. 当前手指有 `親指０/１/２`、其余四指 `１/２/３`。拇指不能按同数字直接对应 KK 段号；先核对关节位置、层级及目标实际权重。缺少親指0 的其他模型不能套此三段配置。

## 最新算法的兼容性

### 可复用的部分

分类后，身体五分区加保留衣物 DYNAMIC 仍构成六类预算；来源是每个顶点的实际有效权重，不依赖骨名是英语还是日语。源捩骨、D 骨等贡献计入相应身体类。手指继续沿用已实现的启用指别与显式映射策略；禁用手指需按当前算法提供非手指重分配，不静默丢弃份额。

均匀身体跟随区域使用语义映射，边缘渐变区域可以使用 Blender 原生最近面插值给出类内初值。两类叠加或未知模式仍不能直接调用自动流程，须回退 Agent 逐顶点分析或人工处理。骨架 profile 不替代逐顶点模式分析，本轮也没有为这些服装批准模式。

数值优化依赖固定姿势下的骨骼变形矩阵，不要求 MMD 和 KK 骨架具有相同节点数或父链，也不要求源素体与目标素体的网格拓扑相同。**当前实现要求原衣物与迁移后衣物保持明确的顶点索引/拓扑对应**，以保留预算并构造形变运输。若删点、细分或改拓扑，须先补对应方案。

### 原始样本的预处理检查项

`kk_vrc_cloth_tools/weights_optimization.py::_rig` 明确拒绝存在 pose constraints 的骨架。原始样本有 70 个，故不能未经处理直接采样；不能仅为通过检查而绕过检查或盲目清空约束。用户计划中的预处理可以清理/转换这些依赖，是否还需要特殊适配由处理后的模型决定。

本轮只读对照当前姿势的完整源 LBS 与 Blender 求值网格，12 个网格最大误差为约 `2.764e-7` Blender 单位，当前所有 matrix_basis 为单位矩阵，A pose 属于当前骨架的静止姿势。**此校验只覆盖当前姿势，不证明转动后的结果或 PMX 原运行环境等价**。

根设置 `use_sdef=true`，但当前 12 个网格均只有一个 Armature 修改器，无 shape keys、SDEF 数据键或形态键驱动，当前表现与 LBS 一致。不能仅凭总开关宣称模型正在使用 SDEF，也不能据此推断原 PMX 从未使用 SDEF。其他带实际 SDEF 校正的 MMD 资产需另立源参考采样约定，现有严格 source-LBS 校验不能静默绕过。[MMD Tools SDEF 实现](https://github.com/MMD-Blender/blender_mmd_tools/blob/main/mmd_tools/core/sdef.py)

### 预处理后的适配次序

1. 先完成用户计划的 T pose 和清理，重新导出拓扑及有效权重。使用本数据表作候选识别，补齐服装任务范围内的 BODY/DYNAMIC/IGNORE/REVIEW 审核，以及实际目标身体的正权重准入表；不要读取全部目标 use_deform 骨当准入。
2. 区分 motion-control map、完整 source-deformation 列表、initial body_map。建立含 parent、追加变换、IK、约束的依赖图；确认是否存在循环或额外动画/驱动。
3. 从处理后的 T pose 静止基准生成对应解剖动作，使用各自静止矩阵和解剖轴，不直接复制 Euler。若入口已成为普通 FK/LBS 模型，复用当前采样流程；只有仍保留 IK、追加变换等特殊依赖时，才需独立适配，避免同一动作重复驱动 FK 与 D 链。
4. 对每个训练/留出动作读取依赖图求值后的所有有效源变形矩阵及实际网格；逐姿势验证 LBS 与 actual_source，保持现有失败停止机制。固定采样物理骨的运动条件；完整时间积分物理验收另行定义，不能用静态矩阵测试冒充物理仿真。
5. 接入现有六类初值、动作优化与末端精调。身体辅助骨不嫁接仍需保留其源参考贡献；衣物动骨只嫁接所需骨链及必要依赖，重新接入目标后检查悬空约束与追加变换引用。不能把导入器 helper 无条件一并复制。
6. 对躯干弯曲、抬臂/前伸/前臂扭转、屈膝与足部旋转，以及启用手指逐类做留出姿势验收。此场景没有实际 KK 目标身体，因此本轮未验证具体目标映射或完成端到端迁移。

MMD 的脚趾/足先EX 是额外注意点：沿用 LEG 预算可行，但若 KK 目标确无独立脚趾自由度，就不能承诺完整复现该独立运动。映射到足部只是可评估的近似，应在源参考与目标可表达性报告中保留残差。

## 复现与文件归档

只读审计脚本：`D:/Program/modding/garment-workflow/tools/audit_mmd_rig.py`。
profile 构建与校验：同目录的 `build_mmd_research_profile.py`、`validate_mmd_research_profile.py`（无 bpy 依赖）。

原始审计与当前姿势数值校验：`D:/Program/modding/garment-workflow/analysis/mmd-to-kk/`。这些是本次 MMD 研究证据，不混入 Neon Vertex 测试项目。

```powershell
python D:/Program/modding/garment-workflow/tools/build_mmd_research_profile.py D:/Program/modding/garment-workflow/analysis/mmd-to-kk/r4_liv_rig_audit.json D:/Program/modding/KK_Modder-BatchTool/bone_profiles
python D:/Program/modding/garment-workflow/tools/validate_mmd_research_profile.py D:/Program/modding/garment-workflow/analysis/mmd-to-kk/r4_liv_rig_audit.json D:/Program/modding/KK_Modder-BatchTool/bone_profiles/mmd_r4_liv_v1.json
```
