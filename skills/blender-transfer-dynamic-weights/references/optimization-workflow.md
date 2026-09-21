# 六类迁移、主体优化与末端精调

## 0.2.3 的新手保守预设

独立 UI 面板提供 `workflow_beginner.apply_preset(p)`：备份旧配置、应用 `optimizer_profiles.CONSERVATIVE_ID` 的参数、扫描/粗识别区域、按身体骨语义生成宏观动作。`beginner_fingers=True` 保留原有手指设计，并非采样增加手指；`beginner_terminal=False` 默认只做主体。预设会重建动作列表，保留角色映射、已验收区域和局部选区。应用后仍须完成角色和区域判断，不能批量确认无法识别项。

`workflow_beginner.start(p)` 做前置检查并写独立初值副本；UI 随后调用 `kkvrc.weight_workflow_solve(automatic=True, include_terminal=...)`，复用原求解器。完成时 `finish_stage(p, stage)` 调用原独立验证，通过才写副本。附加末端阶段要求明确的顶点范围及候选，仍只采样末端动作。自动流程不放松白名单、六类/手指固定份额、拓扑/摘要及验收约束，也不自动保存 blend。

参数记录在版本化 `optimizer_profiles.py` 与每轮 `beginner-run.json`；这只是已测试的起点，不保证新资产适用。缺依赖、未知模式、未验收、过期配置或数值验收失败时停止，保留已生成的中间副本和诊断供处理。不能为了让新手按钮跑通而绕过审核或手改 accepted。

## 0.2.2 的区域模式粗识别

`workflow.analyze_regions(p)` 基于完整原权重与网格边邻接生成 `UNIFORM / EDGE_GRADIENT / REVIEW` 建议。扫描及补充根骨时自动调用，已确认且摘要未过期的区域保持不变。区域字段 `suggestion`、`statistics` 仅记录建议与统计；`mode` 是待确认的实际选择。使用 `workflow.confirm_region(p)` 记录当前区域的验收，需设置 `p.region_index`，且须先完成该区域的模式判断，不得批量盲目确认建议。

均匀判断同时检查归一化身体总份额和身体骨内部占比；渐变判断检查从身体主导边界向自由端的拓扑距离、逆向波动、单调递减拟合和局部跳变。方差/极差不能单独决定模式。纯动骨分片保持零预算，不影响其他分片的判断；根骨下多个独立分片结论不同会返回 REVIEW。均匀底座叠加渐变仍属于未覆盖模式，不能因统计工具存在而直接执行。

统计不自动确认动骨身份，也不提供校准概率。原权重/拓扑/角色/根骨/选区发生变化需重新判断；未确认或过期确认会被 `config` 阻止。旧配置需重新逐区验收，不能通过填造 `reviewed_stamp` 跳过检查。人工确认使用插件函数，不能手工伪造摘要。

## 0.2.1 的根骨区域与动作预设

无自身权重且汇集多条受权重影响支链的组织根自动拆分成支链候选；明确 DYNAMIC 的根保持整体。此规则只是拓扑候选发现，Agent 仍须核对真正的第一节，必要时手动修改区域根。

扫描现在遍历完整源父链，生成以第一节为入口的待确认区域（包含无直接权重的第一节）。已知 BODY/IGNORE 是边界，未知支链仅作候选，仍须确认角色和跟随模式；不能因为自动生成区域就跳过模式适用性判断。重复补充只添加缺失根骨，保留手动区域、模式和选区。

UI 内置上身、下身、全身、腕部动作模板。依据 `VRC_MOTION_SEMANTICS` 或用户指定的源动作语义及目标动作映射生成；源、目标解剖轴独立推导，缺失/退化映射停止或报告跳过项，不默默使用固定世界轴。生成后先预览并恢复姿态；动作幅度可调，手工完整方案仍可用。

`KKVRC_WFMotion.target_parts` 支持目标多骨分摊；为空兼容旧 `target` 单骨配置，非空时比例和须为 1。已识别 KK 脊柱链的胸部模板可自动使用两骨各 0.5，不能把该比例写死用于其他骨架。导出 controls 保留 `axis`，可增加 `source_axis`/`target_axis`；没有独立轴时沿用公共 axis。预览和实际导出使用同一分摊与轴定义。腕部扭转模板包括 ±8/30/50 度；重生成不覆盖已编辑动作。

## 版本、加载与运行环境

插件 0.2 新 UI 的属性入口为 `bpy.context.scene.kkvrc_weight_workflow`，面板位于 KK/VRC Tools。`workflow.py` 负责配置与任务编排；守恒、采样、求解、验收仍由原共享模块实现。仓库、安装目录、Python 已导入模块是三种状态，调用前核对 `__file__`，不要把更新仓库当成已更新面板。

外部 Python 需要 NumPy、SciPy、OSQP。UI 中填写 Python 可执行文件、可选依赖目录，先“检查求解依赖”。不要把 Blender 可执行文件填作 Python。依赖安装需要单独处理，点击求解不会自动联网安装。任务目录保存 run/settings、initial-plan、context、candidate、report、validation、writeback；一轮一目录，不复用错误删骨参考的旧上下文。

## 初值与显式区域

先用完整源快照及真实加权骨建立 BODY/DYNAMIC/IGNORE 等角色。身体辅助骨仍是 BODY；源每个有效变形骨必须计入动作参考。目标身体白名单来自目标素体实际正权重，不根据目标骨架节点数量推断。

UI 的区域由源动骨链生成非零权重顶点，或由“记录当前选区”保存显式顶点索引及拓扑摘要。显式选区覆盖骨链推导范围，允许一链分区；“恢复按骨链取范围”取消覆盖。`MARK_CHAIN` 可以把已确认的衣物骨子链标为动骨，不会把已识别身体骨整链改成动骨。

底层可复用同一个区域解析函数：

```python
from plugin_alias.workflow_regions import resolve_regions
modes = resolve_regions(snapshot['rows'], snapshot['roles'], [
    {'name': 'reviewed_follow', 'mode': 'UNIFORM', 'bones': reviewed_dynamic_bone_names},
    {'name': 'reviewed_join', 'mode': 'EDGE_GRADIENT', 'vertices': reviewed_vertex_ids},
])
plan = wf.prepare_from_body(
    fitted_cloth, snapshot, target_body, body_map, dynamic_map, allowed_body_groups,
    sampling_confidence=confidence_by_vertex,
    source_regions=source_regions, target_regions=target_regions,
    finger_policy=finger_policy, region_modes=modes,
)
```

`bones` 在此 API 中是已展开并确认属于 DYNAMIC 的骨名列表，不是一个空间位置。`resolve_regions` 检查全部源混合顶点的覆盖，阻止冲突与未确认模式。局部高级调用可自行审查范围后向 `prepare_plan(..., indices=..., region_modes=...)` 提交已确认子集；不得把未知范围标为均匀来绕过拦截。

均匀模式初值使用语义映射；渐变模式使用配置的采样可信度，仍按六类预算分配。其含义不是“让整区权重强制相等”，也不是冻结所有身体骨。后续优化用完整原运动参考拟合身体类别内部分布，动骨和启用手指固定。旧 `reviewed_patterns` 字符串只是范围声明，不能代替模式表。

空间采样仅用原生 `POLYINTERP_NEAREST`。目标身体与衣物需处于共同静止姿态。若已存在用户审核过的对应顶点分布，可选“已有目标分布”；否则不能将不明上一轮结果当作可信初值。手指默认不启用：关闭指别需明确映射到同侧非手指骨，开启则保留源份额映射至对应目标指节；同指各节开关一致。

## 两阶段接口

```python
arrays, metadata = api.export_context(
    original_cloth, initial_cloth, target_body,
    roles=roles, bone_map=motion_bone_map,
    source_regions=source_regions, target_regions=target_regions,
    finger_policy=finger_policy, poses=reviewed_pose_specs,
    reviewed_patterns='uniform_and_edge_in_separate_regions',
    reference_anchors=reviewed_source_anchor_map,
)
```

- `body_map` 是初值接收权重的目标骨；`bone_map` 是跨骨架参考/动作对应，不要求两个字典使用同一目标节点。动作控制骨可以是目标辅助父骨，但接受权重的身体骨必须在素体实际权重白名单中。
- `reference_anchors` 仅改变局部解剖参考框架。例如 source support → 所属 Lower_arm。完整 source_weights/source_matrices 仍保存 support 自身响应，不能通过换参考骨删掉它的贡献。
- 两套衣物同顶点拓扑只是必要条件，还需确认索引的语义对应。参考使用世界静止坐标、局部参考框架与适配形变，避免把肢体长度差当成动作误差。
- 源实际 Blender 求值 `actual_source` 与数值源 LBS 不符时中止；目标 LBS 同样核对。目前不支持任意驱动/约束、DQS、活动形态键或多修改器近似。

导出 NPZ/JSON 后用 `optimizer_cli.py CONTEXT_DIR [--contacts]`，OSQP 从审核过的初值求解。UI 在外部隐藏进程运行，Esc 可取消，结果先落文件不直接写衣物。常用宏观动作有较高权重，固定种子随机动作较低权重；独立 holdout 不用于拟合。

末端以主体结果为初值，调用同一 `export_context`，增加：

```python
selected=reviewed_local_vertex_ids,
local_refinement={
    'stage': 'T_pose_terminal_response',
    'region_bones': approved_local_body_bones_by_region,
    'delta_limits': vertex_to_weight_change_cap,
    'pose_bones': {'source': source_endpoint_controls, 'target': target_endpoint_controls},
    'prior': 0.00005, 'smooth': 0.00003, 'residual_scale': 0.15,
    'trust': 0.35, 'max_contact_steps': 8,
}
```

上述数值是现有试验的可用起点，不是普适最优参数。UI 核心修正上限为 1，第一圈 0.25，以后每圈乘 0.24；选区外固定。候选必须是同区域、目标素体实际加权且已经在当前初值候选集合中的非手指骨。末端动作骨从 UI 明确勾选的动作取得，不自动把肩、肘、躯干运动混入末端阶段。世界轴和幅度必须与模型姿态相符；不能只照抄 VRC 某个案例轴向。

## 独立验收和写入

非贴身衣物的 bnip 处理：按用户确认的策略，在原生采样后用 `weights_features.prepare_from_body(sampling_replacements=...)` 将排除组份额补给同侧、素体实际加权的 bust 组，保持躯干预算；不要全组归一化或把这部分交给动骨。当前案例采用所有 bnip 为零并补入同侧 cf_s_bust03。导出优化同时传 `excluded_body_groups`，避免求解重新引入。该参数默认不影响贴身衣物或既有实验；不能把这项规则解释为另行实现体型编辑优化，也不能声称覆盖未采样的形变范围。允许极少 bnip 时需单独实现明确上限，当前严格排除接口不支持非零上限。

读取 candidate/report 后调用 `optimizer_validation.validate(arrays, metadata, candidate, report)`。检查源实际动作一致性、白名单、预算、固定权重、独立姿态响应及范围内顶点/面碰撞。纯动骨只诊断；末端外围也只诊断，但其权重和所有采样位置必须不变。任一与选区接触的跨边界面仍在验收范围。

报告 accepted 后，通过 `api.prepare_optimized_plan(..., destination=independent_copy)` 和 `wf.apply_plan(copy, plan)` 写入；不改写已有签名计划、不手改 accepted。源、目标、身体、配置或候选变化后需要重新准备/求解。UI 修改末端选区不要求重建初值，但导出后修改该阶段设置会使该候选过期。

最终分别报告数值验收、场景可见副本、保存情况和视觉验收。当前检查不证明所有连续姿态、衣物自碰撞或叠穿碰撞均安全。
