# 根据权重特征迁移：Agent API 与六类预算

## 必须满足：目标素体实际权重白名单

身体权重只允许写入目标素体上实际有非零权重、且绑定到目标骨架有效变形骨的组。骨骼存在、`use_deform=True`、Humanoid 身份或关节命名均不足以成为权重候选。保留衣物动骨是单独的显式例外；启用的身体手指骨也必须在素体白名单内。这里是素体全局使用骨集合，不要求每个衣物顶点只能使用某一次最近面采样恰好出现的组；六类、手指及局部白名单仍继续限制分配。

`prepare_plan(..., body_source=target_body_mesh)` 现在必须提供真实目标素体；`prepare_from_body` 自动传入，并将采样候选与实际支持集合取交集。语义映射／回退产生的输出同样检查，不能绕过这一规则。计划包含素体状态和白名单，`apply_plan` 再次核对；不具备该合同的旧计划需重新生成。旧 UI 尚未接入本套 Agent API，不代表旧面板全部获得此检查。

已有违规初值可使用 `prepare_supported_initial(target, body_source, target_regions, dynamic_groups, replacements)`。`replacements` 必须是审核过的同类别语义映射，例如实际身体蒙皮子骨；不能按名称前缀盲猜。只重分配违规身体骨的份额，不全局归一化、不改动骨份额。此操作没有空间插值；需要新的空间采样时仍只用 Blender `POLYINTERP_NEAREST`。

## 预留：类别内部受保护分量

`plan_regions`、`prepare_plan`、`prepare_from_body` 新增 `protected_components=None`。
仅预留扩展入口；任何非 None 参数（包括空字典）立即报 `NotImplementedError`，
不采样、不写入、不静默忽略。暂不固定未来配置 schema。

当同一身体类别同时存在稳定骨骼跟随和其他骨的渐变连接（例如裙子下腰固定影响
加上腰渐变）时，提醒用户实现该能力。现有六类守恒不能保护类别内部这些分量。
当前可对已确认语义的区域保守使用原完整映射，否则保留待决；不能声称自动分解已完成。

## 可选手指保留策略

六类接口新增 `finger_policy` 参数（`prepare_plan`、`prepare_from_body`、
`plan_regions` 均支持）。它包含：

- `source_fingers`：原手指骨组名到指别标识，例如 `THUMB_L`。
- `target_fingers`：目标全部手指骨组名到指别标识，包含不启用的指别。
- `enabled`：允许保留的指别列表，默认空列表。
- `disabled_map`：未启用的原手指骨映射到同侧非手指骨的规则，如手掌。

手指元数据由调用者针对骨架显式提供，不按衣物名称猜测。为兼容既有调用，
完全省略 `finger_policy` 时不识别手指，仍是旧六类行为；非手套迁移应提供完整
元数据和空的 `enabled`，本夹克案例提供 `['THUMB_L', 'THUMB_R']`。

所有采样手指权重均被过滤，启用也不能通过采样增加新的手指影响。
启用的原手指份额先从对应手臂类别中预留，再用原始总有效权重为分母映射回填；
剩余预算执行六类分配。不会先归一化到 1 再追加手指。
未启用的原手指份额通过 `disabled_map` 并入同侧非手指预算，不稀释动骨。
手掌、手腕不属于手指，不整体排除。

返回 `preserved_finger_weights`，记录每顶点应保留的手指权重。原对应指节为零时
不得由采样引入该骨影响；总量、六类预算和逐组写入均验证。映射须确认左右、
指别和指节；相似骨链结构不代表关节变形自动相同，仍需做动作检查。

## 六类预算（衣物迁移推荐入口）

在 `prepare_plan` 或 `prepare_from_body` 中同时传入 `source_regions` 与
`target_regions`，启用逐顶点、逐类别守恒。身体类别为 `TORSO`（含头颈）、
`ARM_L`、`ARM_R`、`LEG_L`、`LEG_R`；保留动骨单独计为第六类。
映射表的键为骨组名，值为类别。肩骨等边界骨须针对实际骨架明确归属；
不按衣物名称或通用名称前缀自动决定类别。

每个类别的新权重总和 = 原类别总量 /（原有效身体总量 + 原保留动骨总量）。
五个身体类别内部允许替换为目标身体分布，动骨仍保留原相对贡献。
原类别为零时不得引入该类别，即使其为最近面插值的主要结果。

采样在类别内分别归一化。`min_region_sample=0.05` 是可调整的候选可靠性阈值：
某类别在整个已归一采样中的份额低于该值时，回退到该类别的原语义映射，
并在 `regional_fallback` 报告；它不会删除或阈值化原类别预算。
这是保守的样本筛选，不是经过标定的解剖置信度。稳定混合特征继续优先语义映射。
代码验证类别映射完整、语义映射不跨类别，并在规划及实际写入后检查类别预算。
返回 `region_budgets` 供 agent 检查。省略区域表仍走旧的仅身体总量守恒接口，
旧 UI 不会自动切换为六类模式，不能把它误当成已接入的新流程。

原生采样仍使用 Blender Data Transfer 的 `POLYINTERP_NEAREST`，临时副本先清空
原顶点组，避免旧组索引污染采样结果。没有引入 Robust、手工最近点插值或权重补全算法。

参考：
- [Robust Skin Weights Transfer via Weight Inpainting](https://www.dgp.toronto.edu/~rinat/projects/RobustSkinWeightsTransfer/preprint.pdf)：用距离和法线筛选对应，再补全未知区；多层衣物反向法线另作处理。
- [Transferring Skin Weights to 3D Scanned Clothes](https://onlinelibrary.wiley.com/doi/full/10.4218/etrij.16.2716.0019)：通过移动截面约束身体与衣物投射，讨论腋下问题。

本实现借鉴拒绝不可信空间对应的原则；没有实现以上论文的求解器。

入口：`kk_vrc_cloth_tools.weights_features`。这是新增的可预览计算与写入接口，未替换旧 UI，也不会自动对已打开的模型执行传权重。旧版“擦除动骨区域身体权重”仍是强制清理工具，不是本流程的后处理步骤。

策略以观察到的权重特征选择，不以“袖带”“下摆”等部件名称选择。袖带可能纯身体、纯动骨或混合，外观名称不能决定算法。

## 守恒的是什么

对每个对应顶点 v，排除非骨组，并按显式策略处理不要的辅助骨之后：

`身体份额 β(v) = 原身体权重总量 / (原身体权重总量 + 原保留动骨权重总量)`

规范化结果满足 `Σ新身体权重(v) = β(v)`，保留动骨各自的相对贡献，总有效变形权重为 1。原数据已归一时，就等价于 `Σ原身体权重(v) = Σ新身体权重(v)`。

它不是全网格总量守恒，也不是每根身体骨的分布必须相同。只守恒总量仍可能把小臂影响错误分到手部，所以身体内部的骨骼语义分布还需约束。原始数值未归一时，不保证原始数值与新数值相等；保留的是有效混合份额。

## 特征与候选

- ZERO_BODY：原身体份额精确为零；任何空间采样都不能增加身体影响。
- BODY_ONLY：身体份额为 1，可在语义映射与可信表面采样之间选择。
- STABLE_MIXED：相邻顶点的身体份额和身体内部语义分布近似稳定。保留语义映射，不用采样打散这个特征；不据此宣称物体为刚体。
- VARYING_MIXED：邻域存在渐变/变化或缺少邻接证据。保留逐顶点身体份额，允许对身体内部候选进行混合。
- UNWEIGHTED：没有已确认的身体/动骨影响，跳过并报告。

稳定性当前使用一环邻接及默认 0.015 容差，是第一阶段局部检测。孤立顶点、断缝和多尺度特征需 agent 查看报告后选择区域，不能将自动特征标签当作已验证材质语义。

空间采样置信度按顶点显式传入，默认 0；0 为语义映射，1 为最近面采样。稳定混合和零身体区域忽略空间采样。候选各自先归一化再混合，最后乘 β(v)。这里不把动骨阈值当作身体删除开关，也不会以距离自动决定解剖可信度。

## 使用流程

```python
from kk_vrc_cloth_tools import weights_features as wf
from kk_vrc_cloth_tools import weight_features as core

# 示例名字只是调用参数，算法不包含这些名称。每个正权重组都必须分类。
roles = {"SourceForearm": "BODY", "ClothChain": "DYNAMIC", "SelectionMask": "IGNORE"}
snapshot = wf.capture_snapshot(original_mesh, roles)
features = core.analyze(snapshot)

body_map = {"SourceForearm": {"TargetForearm": 1.0}}
dynamic_map = {"ClothChain": {"ClothChain": 1.0}}
plan = wf.prepare_from_body(
    target_mesh, snapshot, target_body_mesh, body_map, dynamic_map,
    {"TargetForearm"}, sampling_confidence={0: 0.0, 1: 0.5}, indices=[0, 1])
# 审查 plan 的 summary/features/body_shares/writes/skipped。
report = wf.apply_plan(target_mesh, plan)
```

仅做语义映射或已有采样数组时，使用 `prepare_plan`，无需原生采样临时对象。`prepare_from_body` 复用插件的 Blender 最近面插值采样函数；它恢复选择和模式，不写目标权重，但会临时建立采样网格。对象需在 Object 模式，调用前确认源/目标处于正确的对应坐标和姿态空间。

快照、计划均可 JSON 保存；重用同一源快照重新生成计划，不从上次已改权重再次推断原比例。快照不会自动覆盖，API 返回普通 dict，其完整性通过摘要检查。原始对象与目标必须有一致的顶点索引与拓扑；其他情况须先另建可靠对应。本接口不按最近点猜源权重索引。

## 角色与保护

- BODY：要替换为目标人体骨分布的权重。
- DYNAMIC：保留的衣物变形影响；映射可以显式重命名。
- IGNORE：非变形遮罩，原值保留，不参与预算。
- DROP：用户已决定舍弃的辅助影响，从预算及目标所选顶点移除；不能自动把所有辅助骨标成 DROP。

角色缺失、缺少骨映射、身体/动骨目标重叠、目标名称与遮罩冲突均拒绝生成计划。映射缺失不会通过空间采样悄悄掩盖。源缺失骨组也不自动当成遮罩；可从未受损的原模型保存快照。

写入前检查目标与计划是否一致、目的骨是否实际参与变形、是否有未纳入计划的有效变形组，以及锁定组、共享网格、多个骨架修改器、骨骼包络或修改器掩码等不支持情形。采样源改变也会拒绝旧计划。

只写计划包含的顶点，保护其他顶点和非骨组，失败时回滚本次权重写入。API 不自动保存 blend；实际操作前仍需场景备份。当前未提供包含 locked deform 份额的求解，遇到此类组会报错，需显式制定策略。

## 当前交付范围

非贴身衣物可通过 `prepare_from_body(..., sampling_replacements={源目标组: {替代目标组: 比例}})` 排除局部身体细节，例如把同侧 bnip 采样份额补到实际加权的 bust 组。先用原生最近面插值采样，再在同一六类内部补偿；不能删除后对全体组归一化。替代比例和为 1、目标必须在素体真实权重白名单内，禁止跨类别或循环替代。当前关闭夹克采用 bnip 为零、同侧 cf_s_bust03 接收；少量残留上限尚未实现，不以阈值删除冒充支持。

优化导出传入 `excluded_body_groups`，使这些骨不进入初值、候选及最终写入。此约束不改变源原始身体贡献、六类预算、动骨和启用手指。它是原流程的服装跟随策略，不意味着已验证体型形变骨的编辑范围。

已实现源快照、特征报告、身体总量及六类预算计划、原生面插值候选、显式写入、过期检测、回滚与写后数值检查。六类模式已用于真实敞开夹克试验，并进行了有限姿态检查；数值守恒不等于完整动画验收。

现有 UI 暂未接入六类模式；本轮修复了共用原生采样函数的临时副本组清理。下一阶段可以让 UI 调用同一核心，并加入特征着色、明确的源快照选择和姿态验收。测试命令：

`blender --background --factory-startup --python tests/test_weight_features.py`
