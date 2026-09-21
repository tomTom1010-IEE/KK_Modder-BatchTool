---
name: unity-package-kk-accessories
description: 按固定流程将已完成建模和骨架处理的 KK 饰品从 Blender 导出，在 Unity 中配置 N_move、材质、ChaAccessoryComponent、DynamicBone、Prefab 和饰品表。用于饰品批量打包准备。
---

# KK 饰品打包固定流程

按以下顺序执行。物品名、分组、项目路径、包名、表格起始 ID 使用本次任务指定值，不沿用旧项目值。此流程不包含建模、权重迁移或物理参数调优。

1. **备份与分组**：备份待替换文件；按用户指定的组合导出，其余独立导出。文件名与 Prefab 名一致，使用简单的小写英文单词，如 `wing`、`hair`、`tie`，不加编号或额外后缀。
2. **Blender 导出**：在临时副本上操作，保持源场景不变。带骨架组以指定主骨架的 `ACC_Root` 为中心；硬物体以网格顶点几何中心为中心。平移到原点后，应用对象的位置、旋转和缩放，正确处理父级逆矩阵与蒙皮，使对象原点也在指定中心；不能只把可见几何移动到原点。保留骨链、权重、自定义法向和组内相对位置。FBX 不添加叶骨、不烘焙动画。重新导入验证对象原点、根骨位置和外形，再替换文件。
3. **Unity 导入**：复制最终 FBX 到项目的 `mesh` 目录，保留已有 `.meta`。关闭每个 FBX 的 **Use File Scale** 并 Apply。实例化后删除所有 Animator。
4. **固定层级**：最外层名称为物品名。带骨架饰品将内侧 Armature 对象改名为 `N_move`，形成 `物品名 / N_move / ACC_Root / 动骨链`；网格保留蒙皮绑定，组合中的其他网格保留相对位置。确保 `ACC_Root.localScale = (1,1,1)`，消除缩放时必须补偿层级变换以保持外形。硬物体建立 `物品名 / N_move / 网格`，新增两层空对象使用单位变换，旋转中心仍在几何中心。`N_move` 是命名的 Transform 节点，不是另加 MonoBehaviour。
5. **饰品组件**：在最外层添加 `ChaAccessoryComponent`，将全部 Renderer 填入 `rendNormal`，对应不使用的 `rendAlpha`、`rendHair` 留空。
6. **动骨组件**：调用项目现有 `AutoBoneImplantProcess` 的扫描与添加功能，在最外层添加 DynamicBone，将 `m_Root` 绑定到 `ACC_Root` 的第一层有效子骨。设置根标记 `ACC_Root`、层级 `1`、名称筛选为空、要求 SkinnedMeshRenderer 骨骼依据；关闭分支回退和短骨链过滤，保留单骨饰件，排除无蒙皮依据的辅助链，不重复添加或绑定嵌套根。硬物体不添加 DynamicBone。沿用脚本现有物理默认值。
7. **材质**：保持 Blender 开启，读取每个材质实际使用的主贴图（MMD 材质为 `mmd_base_tex`），先复制到 Unity 项目的 `mesh` 目录，再导入使用。使用项目现有 **`xukmi/MainOpaquePlus`**，只给 `_MainTex` 指定对应主贴图，不把 Toon/Sphere 贴图当主贴图，不自行安装或替换 shader。逐 Renderer、逐材质槽对应，组合饰品不可只套一张贴图。
8. **Prefab 与包名**：保存到项目 `Prefab` 目录，名称与英文物品名一致。通过 AssetImporter 将每个 Prefab 的 AssetBundle 名设为用户指定路径，例如 `chara/tom/liv_empyrea.unity3d`。本流程完成的是 Prefab 和包名配置；实际构建 AssetBundle/zipmod 按用户明确要求执行，不把设置包名报告成已构建。
9. **填表**：沿用饰品 CSV 的表头和模板行，只修改 `ID`（从指定起始值逐行加 1）、`Name`（作品名加饰品英文名）、`MainData`（精确匹配 Prefab 名）。其他列保持不变。已有行名称和 ID 对应正确时，不重复填表或改写。
10. **验收**：通过 Unity 读取保存后的 Prefab，确认 `N_move` 层级、根骨单位缩放、无 Animator、外层 ChaAccessoryComponent、动骨根引用、各槽 shader/主贴图、包名均正确；核对 CSV 与 Prefab 一一对应。报告输出位置及是否实际构建了包。

## 操作接口

Unity 操作使用现有 **Unity Codex Bridge**，通过 `AssetDatabase`、`PrefabUtility`、`SerializedObject` 等 Editor API 执行，不手改 `.prefab`、`.mat`、`.meta`。本地文件桥接使用项目内 `CodexBridge/Inbox` 和 `Outbox`，每次检查返回结果成功后再继续。检索时包含 Git 忽略目录，避免漏掉已安装 shader；缺少入口先查已有配置，不擅自安装替代工具。

仅 Refresh 允许 computer use 点击一次，其余操作通过 Bridge。Unity 5.6 的 Use File Scale 使用 `SerializedObject(ModelImporter).FindProperty("m_UseFileScale")`，Apply 后 `SaveAndReimport()`。表格被 Excel 锁定时请用户关闭该表，解除占用后继续，不强制终止 Excel。
