# MMD 源骨架动作采样接口

`weights_optimization.export_context(..., source_contract=...)` 提供显式的源约束采样入口。

```python
contract = api.source_pose_contract(source_cloth)
arrays, metadata = api.export_context(
    source_cloth, target_cloth, target_body,
    source_contract=contract,
    # 其余角色、区域、动作、手指及映射参数仍须明确提供。
    **reviewed_configuration,
)
```

默认入口仍拒绝有约束的骨架。此可选入口只支持源骨架内自包含的 IK、LIMIT_ROTATION、DAMPED_TRACK、COPY_TRANSFORMS、TRANSFORM；保留约束并读取每个采样姿态的最终变形矩阵，不删除辅助骨权重。拒绝外部目标、缺失骨引用、对象约束、动画/驱动、无限 IK 链和分段 B-Bone。目标骨架仍须满足原入口要求。它不采样物理时间积分，也不支持任意约束系统。

契约记录全部约束参数，导出前后、生成写回计划及实际写回均核对。每个姿态的完整源 LBS 必须与 Blender 实际求值一致；离线求解与独立验证继续执行原有严格检查。MMD 的 `mmd_edge_scale` / `mmd_vertex_order` 只有明确标为非变形 IGNORE 时才排除出优化矩阵，组数据仍保留；真实变形骨不能标 IGNORE。

bnip 无需新增类别：初值继续用 `sampling_replacements` 补给同侧、素体实际有权重的 bust，优化传入 `excluded_body_groups`。不改六类预算或动骨份额。

本例使用当前已贴合、已细分网格的完整原 MMD 权重作为冻结源参考，与目标副本保持完全相同索引。这验证当前适配网格的源骨架运动响应，不等于恢复细分前的原服装外形参考。

回归：`tests/test_optimizer_source_contract_blender.py`，包含默认拒绝、显式约束采样与实际 LBS、非骨骼组排除、过期契约及外部依赖拒绝。

当前 T pose 已有几何相交时，不能靠改变权重修复静止外形。碰撞优化不可行或独立验收失败的候选只能保存诊断，不能绕过 `accepted` 写为最终结果。

## 用户明确接受既有碰撞后的写入

`prepare_optimized_plan(..., existing_collision_authorization="用户明确确认的理由")` 可应用已计算的候选，保留原独立验证报告的 `accepted=false`，不伪造严格无碰撞结论。默认不启用，不能由 Agent 自行推断用户接受。

此入口仍要求全部非碰撞验证通过，并逐姿态核对：候选相交三角形对是初值的子集；穿入采样点及共面歧义计数不增加；最大穿入深度相对初值增加不得超过 1e-6 世界单位。预算、固定份额、候选范围、状态摘要及实际权重写入检查均保持。写入计划记录用户理由、验证摘要与验收范围。
