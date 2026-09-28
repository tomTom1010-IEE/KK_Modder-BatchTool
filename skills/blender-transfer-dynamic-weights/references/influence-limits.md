# 总影响数 API 与验收

适用插件 0.3.0 起；先检查实际加载的模块路径。UI 新建配置默认四影响，已有配置和省略参数的旧 API 仍不限。动骨近似压缩默认关闭。

```python
influence_policy = {
    'max_influences': 4,       # 0 表示不限
    'compress_dynamic': False,
    'dynamic_error_limit': .002,
}
```

优先调用已有 UI 后端 `workflow.prepare / write_initial / export_stage / validate_stage / write_stage`，以保留密集参考、原权重、局部范围和宏观回归证据。

高级调用：

- `influence_blender.limit_initial_plan(plan, influence_policy)`：对已具有六类区域表、身体准入和动骨表的计划准备受限初值，保存 `dense_reference_writes`，重新计算摘要。初值不压缩动骨；缺少动作证据的冲突保留为例外。调用后仍经 `weights_features.apply_plan` 的完整检查。
- `weights_optimization.export_context(..., influence_policy=influence_policy, dense_reference=rows_or_none)`：导出政策；需要压缩时从目标 Blender 骨链采样训练和独立验证探针。`dense_reference` 是按对应顶点排列的稠密六类参考，不是随机权重。
- `optimizer_cli.py` 调用 `weight_optimizer.solve_limited`，先进行有界删除/替换搜索，再冻结支持组合调用现有 OSQP。不要临时重写近似 top-four 脚本。关闭总限值则调用原连续流程。
- `optimizer_validation.validate` 独立检查全网格计数、例外不变、预算、准入、固定贡献、局部上下限、动作和碰撞。压缩还需独立动骨响应/接触检查。UI 末端导出附带上轮宏观 holdout；直接 API 调用需提供同等回归证据。
- 鞋子 `shoe_workflow.run(..., config, ...)` 的 `config['influence_policy']` 使用相同字段。A 保留 `dense-reference.npz`，在总名额内重做连续性；B 固定该支持。不要只数身体条件分布的骨数。

`influence_support` 报告包括 `representation`、`over_limit_vertices`、`maximum`、`export_maximum`。求解的支持报告还含 `exceptions` 的顶点及原因、`compressed_vertices`。状态：

- `UNLIMITED`：未请求总上限。
- `STRICT_FOUR`：全网格数值表示不超过四个正权重。
- `RUNTIME_REVIEW_REQUIRED`：存在保持不变的超限顶点，需要目标运行时/人工判断；不等于可发布的严格四影响结果。

Agent 不自动打开压缩去消除报告中的例外。默认路径可继续处理可行顶点并交付待审副本。只有政策已允许压缩时，才用独立探针评价原动骨子集；失败时不修改报告的 accepted，也不反复用 holdout 选新组合。服装失败候选不写回；鞋子会把失败压缩恢复为未改例外。

独立动骨探针当前为目标骨局部 X/Y/Z 的 12°训练与 −7°验证，每根骨单独动作，Blender 验证 LBS，完整恢复姿态。误差容差是位移除以衣物包围盒跨度，需结合模型尺度审查；它不恢复惯性、阻尼、碰撞参数，也不是所有实际动作的保证。

保留原结果和例外清单。若用户在 Unity 中接受自动限值，记录为单独的视觉或实际导入验收；未读回导入权重前不能沿用裁剪前的逐类别守恒结论。
