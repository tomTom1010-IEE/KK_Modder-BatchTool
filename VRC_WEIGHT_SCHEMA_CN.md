# VRC 骨架与源权重的统一定义

`kk_vrc_cloth_tools/vrc_bone_rules.py` 是角色、父链、avatar 配置、嫁接边界及源权重处理语义的统一入口。`VRC_WEIGHT_POLICIES` 从已有骨骼结构生成，供权重准备和优化使用。不要在测试配置中另维护一份 support 骨黑名单。

这里是本项目识别的命名/模型配置，不是 VRChat 强制所有 avatar 使用这些名字。Unity Humanoid 槽位、模型自有身体变形骨和衣物动骨是不同概念。未知骨、胸部辅助链等必须结合实际绑定判断；不能把非 Humanoid 一律当动骨，也不能把辅助骨一律当无效权重。

## Chocolat 配置补录（2026-09-27）

已只读核对 `Chocolat` 与 `Chocolat_kaihen` 的实际父链、素体及默认衣物的正权重。共同骨名在原记录的 `avatars` 中加入 `AVATAR_CHOCOLAT`；独有的紧凑手指名和胸链单独登记，保留原 `VrcBoneRule` 字段及 Shinano 配置。

同名 `Hand`、`Foot` 的父链在两种 avatar 中不同：通过 `VRC_BONE_PARENT_OVERRIDES` 和 `vrc_bone_parents` 显式记录，不覆盖原 `parent`。审查函数可指定 avatar；未指定时仅接受已维护的父链变体。

本次导入使用 `Breast_L/R.001` 等名称，并不是用户截图的 `Breast_L/R_001`。不作全局标点替换猜测。默认衣物、毛发及附属肢体骨链不混入身体规则；无权重的 `_end` 身体末端标记为锚点并保持 REVIEW，不当作缺失的手指末节或脚趾。

详细观察、数据范围及目标映射边界见 [Chocolat profile](docs/chocolat-bone-profile.md)。

2026-09-28：源命名统一由 `VRC_BODY_SEMANTICS` 表达解剖槽位；`vrc_kk_mapping.py` 用一套 KK 目标表生成两种 avatar 共用的默认映射。六类扫描、旧身体映射、新手手指设置及嫁接父级映射共用该数据，不为 Chocolat 另建传递算法。宏观动作槽位与六类预算未扩展；两种素体的胸骨权重／动作映射保持同一人工配置边界，胸根挂接映射不等于权重对应。

## 两张拓扑表的定位

- `Armature_armature_topology_VRC.json`：历史 VRC 样本的完整拓扑快照，603 根骨。
- `Armature_armature_topology_KK.json`：历史目标身体拓扑快照，181 根骨。

2026-09-18 核对当前场景：源 Armature 为 123 根骨，与 VRC 历史表重合 35 根，重合骨父链无差异；目标 Armature.001 为 245 根，包含 KK 表全部 181 根，重合骨父链无差异。数量不同来自具体资产/骨架组成不同，不应以当前精简场景覆盖历史完整表，也不应复制其坐标作为通用模板。

历史表已有四根 Upper/Lower_arm_support.L/R，标记 use_deform=true，分别隶属同侧 Upper/Lower_arm。现有 VRC 规则也已识别其身体辅助用途；本轮修复的是权重流程与定义脱节的问题。当前源夹克有 58 个有效加权骨：17 个身体、41 个本案例已确认保留的动骨。该数量与实际权重统计属于测试报告，不写死为 VRC 规范。

## 权重策略字段

| 字段 | 含义 |
|---|---|
| source_role | BODY 或 REVIEW；REVIEW 必须由实际资产确认，不能自动降为 DROP |
| budget_region | 躯干或左右四肢的预算归属；手指仍遵循独立指别策略 |
| reference_anchor | 对齐动作的解剖参考骨；support 使用所属上下臂的参考框架 |
| preserve_source_deformation | 构造源运动参考时保留实际变形贡献 |
| graft_source_bone | 是否直接嫁接原身体骨；与是否保留其变形贡献相互独立 |
| target_admission | 目标端只允许目标素体真实存在正权重的身体骨；已审核衣物动骨另行处理 |

四根 arm support 的源权重属于同侧 ARM 预算。采样仍使用每根 support 自己的实际变形矩阵，而不是删除后归一化，也不是默认把 support 的位置当作手腕枢轴。其父骨作为跨素体参考框架；只有确认所有相关姿势中变形等价后，才可将其权重合并到父骨。

`audit_vrc_weight_roles` 将已知身体骨的错误 DROP/IGNORE、父链差异、未知加权名称分别报告。运行时需要检查真实 parent/use_deform/正权重以及约束与驱动。优化导出禁止静默排除有效源变形骨，并采样 `actual_source`；求解前将完整源 LBS 与 Blender 实际结果逐姿势比较，误差超过阈值则中止。目标白名单在准备、导出和写回阶段继续检查。

不能把嫁接时“不复制原身体辅助骨”的规则，误用于源运动参考中的“删掉该骨权重”。即使六类预算守恒，同一 ARM 内错误放大手腕也会导致明显形变，因此需要实际源动作验证。
