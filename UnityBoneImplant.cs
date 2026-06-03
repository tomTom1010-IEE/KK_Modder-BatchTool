using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEditor;
using UnityEngine;

public class AutoBoneImplantProcess : EditorWindow
{
    private const string DefaultPrefixes =
        "skirt_,sleeve_,ribbon_,cape_,tail_,hair_,cloth_,add_,vrc_,acc_,breast_,belt_";

    private GameObject rootObject;
    private bool usePrefixFilter;
    private bool requireSkinnedBoneEvidence = true;
    private bool ignoreExisting = true;
    private bool addDynamicBoneComponents;
    private bool ignoreExistingDynamicBones = true;
    private DynamicBoneBindMode dynamicBoneBindMode = DynamicBoneBindMode.ImplantRoots;
    private int hairDynamicBoneLevel = 1;
    private string hairRootMarkers = "root";
    private string hairNameMarkers = "hair";
    private bool hairUseBranchFallback = true;
    private bool hairRequireSkinnedBoneEvidence = true;
    private bool hairIgnoreExistingDynamicBones = true;
    private string customPrefixes = DefaultPrefixes;
    private Vector2 previewScroll;
    private Vector2 hairPreviewScroll;
    private List<ImplantCandidate> preview = new List<ImplantCandidate>();
    private List<HairDynamicBoneCandidate> hairPreview = new List<HairDynamicBoneCandidate>();

    private enum DynamicBoneBindMode
    {
        ImplantRoots,
        FirstLevelChildren
    }

    // Koikatsu vanilla body bones exported from Armature_armature_topology_KK.json.
    // Keep this as a hard standard to avoid treating custom cf_j_/cf_d_/cf_s_ clothes bones as vanilla bones.
    private static readonly HashSet<string> VanillaBones = new HashSet<string>
    {
        "cf_d_ana",
        "cf_d_arm01_L",
        "cf_d_arm01_R",
        "cf_d_arm02_L",
        "cf_d_arm02_R",
        "cf_d_arm03_L",
        "cf_d_arm03_R",
        "cf_d_bnip01_L",
        "cf_d_bnip01_R",
        "cf_d_bust00",
        "cf_d_bust01_L",
        "cf_d_bust01_R",
        "cf_d_bust02_L",
        "cf_d_bust02_R",
        "cf_d_bust03_L",
        "cf_d_bust03_R",
        "cf_d_forearm02_L",
        "cf_d_forearm02_R",
        "cf_d_hand_L",
        "cf_d_hand_R",
        "cf_d_kneeF_L",
        "cf_d_kneeF_R",
        "cf_d_kokan",
        "cf_d_leg02_L",
        "cf_d_leg02_R",
        "cf_d_leg03_L",
        "cf_d_leg03_R",
        "cf_d_shoulder02_L",
        "cf_d_shoulder02_R",
        "cf_d_shoulder_L",
        "cf_d_shoulder_R",
        "cf_d_siri01_L",
        "cf_d_siri01_R",
        "cf_d_siri_L",
        "cf_d_siri_R",
        "cf_d_thigh01_L",
        "cf_d_thigh01_R",
        "cf_d_thigh02_L",
        "cf_d_thigh02_R",
        "cf_d_thigh03_L",
        "cf_d_thigh03_R",
        "cf_d_wrist_L",
        "cf_d_wrist_R",
        "cf_j_ana",
        "cf_j_arm00_L",
        "cf_j_arm00_R",
        "cf_j_bnip02_L",
        "cf_j_bnip02_R",
        "cf_j_bnip02root_L",
        "cf_j_bnip02root_R",
        "cf_j_bust01_L",
        "cf_j_bust01_R",
        "cf_j_bust02_L",
        "cf_j_bust02_R",
        "cf_j_bust03_L",
        "cf_j_bust03_R",
        "cf_j_foot_L",
        "cf_j_foot_R",
        "cf_j_forearm01_L",
        "cf_j_forearm01_R",
        "cf_j_hand_L",
        "cf_j_hand_R",
        "cf_j_head",
        "cf_j_hips",
        "cf_j_index01_L",
        "cf_j_index01_R",
        "cf_j_index02_L",
        "cf_j_index02_R",
        "cf_j_index03_L",
        "cf_j_index03_R",
        "cf_j_kokan",
        "cf_j_leg01_L",
        "cf_j_leg01_R",
        "cf_j_leg03_L",
        "cf_j_leg03_R",
        "cf_j_little01_L",
        "cf_j_little01_R",
        "cf_j_little02_L",
        "cf_j_little02_R",
        "cf_j_little03_L",
        "cf_j_little03_R",
        "cf_j_middle01_L",
        "cf_j_middle01_R",
        "cf_j_middle02_L",
        "cf_j_middle02_R",
        "cf_j_middle03_L",
        "cf_j_middle03_R",
        "cf_j_neck",
        "cf_j_ring01_L",
        "cf_j_ring01_R",
        "cf_j_ring02_L",
        "cf_j_ring02_R",
        "cf_j_ring03_L",
        "cf_j_ring03_R",
        "cf_j_root",
        "cf_j_shoulder_L",
        "cf_j_shoulder_R",
        "cf_j_siri_L",
        "cf_j_siri_R",
        "cf_j_spine01",
        "cf_j_spine02",
        "cf_j_spine03",
        "cf_j_thigh00_L",
        "cf_j_thigh00_R",
        "cf_j_thumb01_L",
        "cf_j_thumb01_R",
        "cf_j_thumb02_L",
        "cf_j_thumb02_R",
        "cf_j_thumb03_L",
        "cf_j_thumb03_R",
        "cf_j_toes_L",
        "cf_j_toes_R",
        "cf_j_waist01",
        "cf_j_waist02",
        "cf_n_height",
        "cf_o_root",
        "cf_s_ana",
        "cf_s_arm01_L",
        "cf_s_arm01_R",
        "cf_s_arm02_L",
        "cf_s_arm02_R",
        "cf_s_arm03_L",
        "cf_s_arm03_R",
        "cf_s_bnip015_L",
        "cf_s_bnip015_R",
        "cf_s_bnip01_L",
        "cf_s_bnip01_R",
        "cf_s_bnip025_L",
        "cf_s_bnip025_R",
        "cf_s_bnip02_L",
        "cf_s_bnip02_R",
        "cf_s_bust00_L",
        "cf_s_bust00_R",
        "cf_s_bust01_L",
        "cf_s_bust01_R",
        "cf_s_bust02_L",
        "cf_s_bust02_R",
        "cf_s_bust03_L",
        "cf_s_bust03_R",
        "cf_s_elbo_L",
        "cf_s_elbo_R",
        "cf_s_elboback_L",
        "cf_s_elboback_R",
        "cf_s_forearm01_L",
        "cf_s_forearm01_R",
        "cf_s_forearm02_L",
        "cf_s_forearm02_R",
        "cf_s_hand_L",
        "cf_s_hand_R",
        "cf_s_head",
        "cf_s_kneeB_L",
        "cf_s_kneeB_R",
        "cf_s_leg01_L",
        "cf_s_leg01_R",
        "cf_s_leg02_L",
        "cf_s_leg02_R",
        "cf_s_leg03_L",
        "cf_s_leg03_R",
        "cf_s_leg_L",
        "cf_s_leg_R",
        "cf_s_neck",
        "cf_s_shoulder02_L",
        "cf_s_shoulder02_R",
        "cf_s_siri_L",
        "cf_s_siri_R",
        "cf_s_spine01",
        "cf_s_spine02",
        "cf_s_spine03",
        "cf_s_thigh01_L",
        "cf_s_thigh01_R",
        "cf_s_thigh02_L",
        "cf_s_thigh02_R",
        "cf_s_thigh03_L",
        "cf_s_thigh03_R",
        "cf_s_waist01",
        "cf_s_waist02",
        "cf_s_wrist_L",
        "cf_s_wrist_R",
        "n_body",
        "o_body_a",
        "p_cf_body_00"
    };

    private static readonly HashSet<string> IgnoredTransformNames = new HashSet<string>
    {
        "Armature",
        "Root",
        "root",
        "Skeleton",
        "skeleton",
        "BodyTop",
        "Clothes",
        "ClothesRoot",
        "Renderer",
        "Mesh",
        "Meshes",
        "cf_o_root",
        "p_cf_body_bone"
    };

    [MenuItem("Tools/KK Mods/Auto Bone Implant")]
    public static void ShowWindow()
    {
        GetWindow<AutoBoneImplantProcess>("Auto Bone Implant");
    }

    private void OnGUI()
    {
        EditorGUILayout.LabelField("Root", EditorStyles.boldLabel);
        rootObject = (GameObject)EditorGUILayout.ObjectField("Root Object", rootObject, typeof(GameObject), true);

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Detection", EditorStyles.boldLabel);
        usePrefixFilter = EditorGUILayout.ToggleLeft("Only include custom bones with these prefixes", usePrefixFilter);

        EditorGUI.BeginDisabledGroup(!usePrefixFilter);
        customPrefixes = EditorGUILayout.TextField("Prefixes", customPrefixes);
        EditorGUI.EndDisabledGroup();

        requireSkinnedBoneEvidence = EditorGUILayout.ToggleLeft(
            "Require SkinnedMeshRenderer bone evidence",
            requireSkinnedBoneEvidence);

        ignoreExisting = EditorGUILayout.ToggleLeft("Skip candidates that already have BoneImplantProcess", ignoreExisting);

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Dynamic Bone", EditorStyles.boldLabel);
        addDynamicBoneComponents = EditorGUILayout.ToggleLeft("Add/Update Dynamic Bone components after implant", addDynamicBoneComponents);

        EditorGUI.BeginDisabledGroup(!addDynamicBoneComponents);
        dynamicBoneBindMode = (DynamicBoneBindMode)EditorGUILayout.EnumPopup("Bind Roots", dynamicBoneBindMode);
        ignoreExistingDynamicBones = EditorGUILayout.ToggleLeft("Skip existing Dynamic Bone roots", ignoreExistingDynamicBones);
        EditorGUI.EndDisabledGroup();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Hair Dynamic Bone", EditorStyles.boldLabel);
        hairRootMarkers = EditorGUILayout.TextField("Root markers", hairRootMarkers);
        hairNameMarkers = EditorGUILayout.TextField("Hair name markers", hairNameMarkers);
        hairDynamicBoneLevel = EditorGUILayout.IntField("Bind level after nearest root", hairDynamicBoneLevel);
        if (hairDynamicBoneLevel < 1)
            hairDynamicBoneLevel = 1;
        hairUseBranchFallback = EditorGUILayout.ToggleLeft(
            "Fallback: count from unbranched chain starts",
            hairUseBranchFallback);
        hairRequireSkinnedBoneEvidence = EditorGUILayout.ToggleLeft(
            "Require SkinnedMeshRenderer bone evidence",
            hairRequireSkinnedBoneEvidence);
        hairIgnoreExistingDynamicBones = EditorGUILayout.ToggleLeft(
            "Skip existing Dynamic Bone roots",
            hairIgnoreExistingDynamicBones);

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Scan Hair Preview"))
        {
            ScanHairDynamicBonePreview();
        }

        EditorGUI.BeginDisabledGroup(hairPreview.Count == 0);
        if (GUILayout.Button("Apply Hair Dynamic Bones"))
        {
            ApplyHairDynamicBonePreview();
        }
        EditorGUI.EndDisabledGroup();
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();
        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Scan Preview"))
        {
            ScanPreview();
        }

        EditorGUI.BeginDisabledGroup(preview.Count == 0);
        if (GUILayout.Button("Apply Preview"))
        {
            ApplyPreview();
        }
        EditorGUI.EndDisabledGroup();
        EditorGUILayout.EndHorizontal();

        DrawPreview();
        DrawHairDynamicBonePreview();
    }

    private void ScanPreview()
    {
        preview.Clear();

        if (rootObject == null)
        {
            Debug.LogError("Please assign a root object first.");
            return;
        }

        Type bipType = FindTypeByName("BoneImplantProcess");
        if (bipType == null)
        {
            Debug.LogError("BoneImplantProcess type not found. Make sure KoikatsuModdingTools / ModBoneImplantor is imported.");
            return;
        }

        HashSet<Transform> skinnedBones = CollectSkinnedBones(rootObject);
        string[] prefixes = ParsePrefixes(customPrefixes);
        Transform[] allTransforms = rootObject.GetComponentsInChildren<Transform>(true);

        foreach (Transform bone in allTransforms)
        {
            ImplantCandidate candidate = TryCreateCandidate(bone, bipType, skinnedBones, prefixes);
            if (candidate != null)
                preview.Add(candidate);
        }

        Debug.Log("Auto Bone Implant preview found " + preview.Count + " candidate(s).");
    }

    private void ScanHairDynamicBonePreview()
    {
        hairPreview.Clear();

        if (rootObject == null)
        {
            Debug.LogError("Please assign a root object first.");
            return;
        }

        Type dynamicBoneType = FindTypeByName("DynamicBone");
        HashSet<Transform> skinnedBones = CollectSkinnedBones(rootObject);
        string[] rootMarkers = ParsePrefixes(hairRootMarkers);
        string[] nameMarkers = ParsePrefixes(hairNameMarkers);
        Transform[] allTransforms = rootObject.GetComponentsInChildren<Transform>(true);

        foreach (Transform bone in allTransforms)
        {
            HairDynamicBoneCandidate candidate = TryCreateHairDynamicBoneCandidate(
                bone,
                dynamicBoneType,
                skinnedBones,
                rootMarkers,
                nameMarkers);
            AddUniqueHairCandidate(candidate);
        }

        if (hairUseBranchFallback)
        {
            foreach (Transform bone in allTransforms)
            {
                HairDynamicBoneCandidate candidate = TryCreateHairFallbackDynamicBoneCandidate(
                    bone,
                    dynamicBoneType,
                    skinnedBones,
                    nameMarkers);
                AddUniqueHairCandidate(candidate);
            }
        }

        Debug.Log("Hair DynamicBone preview found " + hairPreview.Count + " candidate(s).");
    }

    private void AddUniqueHairCandidate(HairDynamicBoneCandidate candidate)
    {
        if (candidate == null || candidate.Root == null)
            return;

        foreach (HairDynamicBoneCandidate existing in hairPreview)
        {
            if (existing != null && existing.Root == candidate.Root)
                return;
        }

        hairPreview.Add(candidate);
    }

    private ImplantCandidate TryCreateCandidate(
        Transform bone,
        Type bipType,
        HashSet<Transform> skinnedBones,
        string[] prefixes)
    {
        if (bone == null || bone.parent == null)
            return null;

        if (IgnoredTransformNames.Contains(bone.name))
            return null;

        bool selfIsVanilla = IsVanillaBoneName(bone.name);
        bool parentIsVanilla = IsVanillaBoneName(bone.parent.name);

        if (selfIsVanilla || !parentIsVanilla)
            return null;

        bool hasExistingComponent = HasExistingBoneImplantProcess(bipType, rootObject, bone);

        if (ignoreExisting && hasExistingComponent)
            return null;

        if (usePrefixFilter && !HasAnyPrefix(bone.name, prefixes))
            return null;

        bool hasBoneEvidence = HasBoneEvidence(bone, skinnedBones);
        if (requireSkinnedBoneEvidence && !hasBoneEvidence)
            return null;

        return new ImplantCandidate
        {
            Source = bone,
            Destination = bone.parent,
            HasSkinnedBoneEvidence = hasBoneEvidence,
            HasExistingComponent = hasExistingComponent
        };
    }

    private void ApplyPreview()
    {
        if (rootObject == null)
        {
            Debug.LogError("Please assign a root object first.");
            return;
        }

        Type bipType = FindTypeByName("BoneImplantProcess");
        if (bipType == null)
        {
            Debug.LogError("BoneImplantProcess type not found. Make sure KoikatsuModdingTools / ModBoneImplantor is imported.");
            return;
        }

        Type dynamicBoneType = null;
        if (addDynamicBoneComponents)
        {
            dynamicBoneType = FindTypeByName("DynamicBone");
            if (dynamicBoneType == null)
            {
                Debug.LogError("DynamicBone type not found. Import Dynamic Bone first or disable Dynamic Bone creation.");
                return;
            }
        }

        int added = 0;
        int failed = 0;
        int dynamicAdded = 0;
        int dynamicSkipped = 0;
        int dynamicFailed = 0;

        foreach (ImplantCandidate candidate in preview)
        {
            if (candidate == null || candidate.Source == null || candidate.Destination == null)
                continue;

            if (AddOrUpdateBoneImplantProcess(bipType, rootObject, candidate.Source, candidate.Destination))
                added++;
            else
                failed++;

            if (addDynamicBoneComponents && dynamicBoneType != null)
            {
                DynamicBoneApplyResult result = AddDynamicBonesForCandidate(dynamicBoneType, rootObject, candidate.Source);
                dynamicAdded += result.AddedOrUpdated;
                dynamicSkipped += result.Skipped;
                dynamicFailed += result.Failed;
            }
        }

        EditorUtility.SetDirty(rootObject);
        Debug.Log("Auto BoneImplantProcess finished. Added/Updated: " + added + ", Failed: " + failed);
        if (addDynamicBoneComponents)
        {
            Debug.Log(
                "Auto DynamicBone finished. Added/Updated: " + dynamicAdded +
                ", Skipped: " + dynamicSkipped +
                ", Failed: " + dynamicFailed);
        }
        ScanPreview();
    }

    private void ApplyHairDynamicBonePreview()
    {
        if (rootObject == null)
        {
            Debug.LogError("Please assign a root object first.");
            return;
        }

        Type dynamicBoneType = FindTypeByName("DynamicBone");
        if (dynamicBoneType == null)
        {
            Debug.LogError("DynamicBone type not found. Import Dynamic Bone first.");
            return;
        }

        int added = 0;
        int skipped = 0;
        int failed = 0;

        foreach (HairDynamicBoneCandidate candidate in hairPreview)
        {
            if (candidate == null || candidate.Root == null)
                continue;

            Component existing = FindExistingDynamicBone(dynamicBoneType, rootObject, candidate.Root);
            if (existing != null && hairIgnoreExistingDynamicBones)
            {
                skipped++;
                continue;
            }

            if (AddOrUpdateDynamicBone(dynamicBoneType, rootObject, candidate.Root, existing))
                added++;
            else
                failed++;
        }

        EditorUtility.SetDirty(rootObject);
        Debug.Log("Hair DynamicBone finished. Added/Updated: " + added + ", Skipped: " + skipped + ", Failed: " + failed);
        ScanHairDynamicBonePreview();
    }

    private void DrawPreview()
    {
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Preview (" + preview.Count + ")", EditorStyles.boldLabel);

        if (preview.Count == 0)
        {
            EditorGUILayout.HelpBox("Scan to preview custom bone roots before adding components.", MessageType.Info);
            return;
        }

        previewScroll = EditorGUILayout.BeginScrollView(previewScroll, GUILayout.MinHeight(180));

        foreach (ImplantCandidate candidate in preview)
        {
            if (candidate == null || candidate.Source == null || candidate.Destination == null)
                continue;

            string evidence = candidate.HasSkinnedBoneEvidence ? "weighted/descendant weighted" : "no renderer evidence";
            string existing = candidate.HasExistingComponent ? ", existing component" : "";
            string dynamicRoots = "";
            if (addDynamicBoneComponents)
                dynamicRoots = ", dynamic roots: " + CountDynamicRoots(candidate.Source);
            EditorGUILayout.LabelField(candidate.Source.name + " -> " + candidate.Destination.name + " (" + evidence + existing + dynamicRoots + ")");
        }

        EditorGUILayout.EndScrollView();
    }

    private void DrawHairDynamicBonePreview()
    {
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Hair Dynamic Bone Preview (" + hairPreview.Count + ")", EditorStyles.boldLabel);

        if (hairPreview.Count == 0)
        {
            EditorGUILayout.HelpBox("Scan to preview hair Dynamic Bone roots found by nearest Root marker and level.", MessageType.Info);
            return;
        }

        hairPreviewScroll = EditorGUILayout.BeginScrollView(hairPreviewScroll, GUILayout.MinHeight(160));

        foreach (HairDynamicBoneCandidate candidate in hairPreview)
        {
            if (candidate == null || candidate.Root == null || candidate.NearestRoot == null)
                continue;

            string evidence = candidate.HasSkinnedBoneEvidence ? "weighted/descendant weighted" : "no renderer evidence";
            string existing = candidate.HasExistingDynamicBone ? ", existing DynamicBone" : "";
            EditorGUILayout.LabelField(
                candidate.Root.name +
                " <- " +
                candidate.SourceLabel +
                " " +
                candidate.NearestRoot.name +
                ", level " +
                candidate.Level +
                " (" +
                evidence +
                existing +
                ")");
        }

        EditorGUILayout.EndScrollView();
    }

    private static bool AddOrUpdateBoneImplantProcess(
        Type bipType,
        GameObject targetObject,
        Transform trfSrc,
        Transform trfDst)
    {
        Component comp = FindExistingBoneImplantProcess(bipType, targetObject, trfSrc);
        if (comp == null)
        {
            comp = Undo.AddComponent(targetObject, bipType);
        }
        else
        {
            Undo.RecordObject(comp, "Update BoneImplantProcess");
        }

        FieldInfo srcField = bipType.GetField("trfSrc", BindingFlags.Public | BindingFlags.Instance);
        FieldInfo dstField = bipType.GetField("trfDst", BindingFlags.Public | BindingFlags.Instance);

        if (srcField == null || dstField == null)
        {
            Debug.LogError("Could not find trfSrc or trfDst fields on BoneImplantProcess.");
            return false;
        }

        srcField.SetValue(comp, trfSrc);
        dstField.SetValue(comp, trfDst);

        EditorUtility.SetDirty(targetObject);
        Debug.Log("BoneImplantProcess on " + targetObject.name + ": " + trfSrc.name + " -> parent " + trfDst.name);
        return true;
    }

    private DynamicBoneApplyResult AddDynamicBonesForCandidate(Type dynamicBoneType, GameObject hostObject, Transform implantRoot)
    {
        DynamicBoneApplyResult result = new DynamicBoneApplyResult();
        List<Transform> roots = GetDynamicBoneRoots(implantRoot);

        foreach (Transform root in roots)
        {
            if (root == null)
                continue;

            Component existing = FindExistingDynamicBone(dynamicBoneType, hostObject, root);
            if (existing != null && ignoreExistingDynamicBones)
            {
                result.Skipped++;
                continue;
            }

            if (AddOrUpdateDynamicBone(dynamicBoneType, hostObject, root, existing))
                result.AddedOrUpdated++;
            else
                result.Failed++;
        }

        return result;
    }

    private bool AddOrUpdateDynamicBone(Type dynamicBoneType, GameObject hostObject, Transform root, Component existing)
    {
        Component comp = existing;
        if (comp == null)
        {
            comp = Undo.AddComponent(hostObject, dynamicBoneType);
        }
        else
        {
            Undo.RecordObject(comp, "Update DynamicBone");
        }

        FieldInfo rootField = FindDynamicBoneRootField(dynamicBoneType);
        if (rootField == null)
        {
            Debug.LogError("Could not find DynamicBone root field. Expected m_Root or Root.");
            return false;
        }

        rootField.SetValue(comp, root);
        EditorUtility.SetDirty(hostObject);
        Debug.Log("DynamicBone on " + hostObject.name + ": root " + root.name);
        return true;
    }

    private Component FindExistingDynamicBone(Type dynamicBoneType, GameObject hostObject, Transform root)
    {
        if (dynamicBoneType == null || hostObject == null || root == null)
            return null;

        FieldInfo rootField = FindDynamicBoneRootField(dynamicBoneType);
        if (rootField == null)
            return null;

        Component[] components = hostObject.GetComponents(dynamicBoneType);
        foreach (Component component in components)
        {
            if (component == null)
                continue;

            Transform existingRoot = rootField.GetValue(component) as Transform;
            if (existingRoot == root)
                return component;
        }

        return null;
    }

    private HairDynamicBoneCandidate TryCreateHairDynamicBoneCandidate(
        Transform bone,
        Type dynamicBoneType,
        HashSet<Transform> skinnedBones,
        string[] rootMarkers,
        string[] nameMarkers)
    {
        if (bone == null || bone.parent == null)
            return null;

        if (IsRootMarkerName(bone.name, rootMarkers))
            return null;

        Transform nearestRoot = FindNearestRootMarkerAncestor(bone, rootMarkers);
        if (nearestRoot == null)
            return null;

        if (!HasHairNameMarkerBetween(nearestRoot, bone, nameMarkers))
            return null;

        int level = GetAncestorDistance(bone, nearestRoot);
        if (level != hairDynamicBoneLevel)
            return null;

        bool hasBoneEvidence = HasBoneEvidence(bone, skinnedBones);
        if (hairRequireSkinnedBoneEvidence && !hasBoneEvidence)
            return null;

        bool hasExistingDynamicBone = dynamicBoneType != null && FindExistingDynamicBone(dynamicBoneType, rootObject, bone) != null;
        if (hairIgnoreExistingDynamicBones && hasExistingDynamicBone)
            return null;

        return new HairDynamicBoneCandidate
        {
            Root = bone,
            NearestRoot = nearestRoot,
            Level = level,
            SourceLabel = "nearest root",
            HasSkinnedBoneEvidence = hasBoneEvidence,
            HasExistingDynamicBone = hasExistingDynamicBone
        };
    }

    private HairDynamicBoneCandidate TryCreateHairFallbackDynamicBoneCandidate(
        Transform bone,
        Type dynamicBoneType,
        HashSet<Transform> skinnedBones,
        string[] nameMarkers)
    {
        if (bone == null || bone.parent == null)
            return null;

        if (!HasHairNameMarkerBetween(bone, bone, nameMarkers))
            return null;

        Transform chainStart = FindUnbranchedChainStart(bone);
        if (chainStart == null)
            return null;

        int level = GetAncestorDistance(bone, chainStart) + 1;
        if (level != hairDynamicBoneLevel)
            return null;

        bool hasBoneEvidence = HasBoneEvidence(bone, skinnedBones);
        if (hairRequireSkinnedBoneEvidence && !hasBoneEvidence)
            return null;

        bool hasExistingDynamicBone = dynamicBoneType != null && FindExistingDynamicBone(dynamicBoneType, rootObject, bone) != null;
        if (hairIgnoreExistingDynamicBones && hasExistingDynamicBone)
            return null;

        return new HairDynamicBoneCandidate
        {
            Root = bone,
            NearestRoot = chainStart,
            Level = level,
            SourceLabel = "chain start",
            HasSkinnedBoneEvidence = hasBoneEvidence,
            HasExistingDynamicBone = hasExistingDynamicBone
        };
    }

    private static Transform FindNearestRootMarkerAncestor(Transform bone, string[] rootMarkers)
    {
        Transform current = bone.parent;
        while (current != null)
        {
            if (IsRootMarkerName(current.name, rootMarkers))
                return current;
            current = current.parent;
        }

        return null;
    }

    private static int GetAncestorDistance(Transform bone, Transform ancestor)
    {
        int distance = 0;
        Transform current = bone;
        while (current != null && current != ancestor)
        {
            distance++;
            current = current.parent;
        }

        return current == ancestor ? distance : -1;
    }

    private static Transform FindUnbranchedChainStart(Transform bone)
    {
        Transform current = bone;
        while (current.parent != null && current.parent.childCount == 1)
        {
            current = current.parent;
        }

        if (current == bone && bone.parent != null && bone.parent.childCount == 1)
            return null;

        return current;
    }

    private static bool IsRootMarkerName(string name, string[] rootMarkers)
    {
        if (string.IsNullOrEmpty(name))
            return false;

        if (rootMarkers == null || rootMarkers.Length == 0)
            return name.IndexOf("root", StringComparison.OrdinalIgnoreCase) >= 0;

        foreach (string marker in rootMarkers)
        {
            if (string.IsNullOrEmpty(marker))
                continue;
            if (name.IndexOf(marker, StringComparison.OrdinalIgnoreCase) >= 0)
                return true;
        }

        return false;
    }

    private static bool HasHairNameMarkerBetween(Transform nearestRoot, Transform bone, string[] nameMarkers)
    {
        if (nameMarkers == null || nameMarkers.Length == 0)
            return true;

        Transform current = bone;
        while (current != null)
        {
            if (HasAnyNameMarker(current.name, nameMarkers))
                return true;
            if (current == nearestRoot)
                break;
            current = current.parent;
        }

        return false;
    }

    private static bool HasAnyNameMarker(string name, string[] markers)
    {
        if (string.IsNullOrEmpty(name) || markers == null)
            return false;

        foreach (string marker in markers)
        {
            if (string.IsNullOrEmpty(marker))
                continue;
            if (name.IndexOf(marker, StringComparison.OrdinalIgnoreCase) >= 0)
                return true;
        }

        return false;
    }

    private static FieldInfo FindDynamicBoneRootField(Type dynamicBoneType)
    {
        FieldInfo rootField = dynamicBoneType.GetField("m_Root", BindingFlags.Public | BindingFlags.Instance);
        if (rootField != null)
            return rootField;

        return dynamicBoneType.GetField("Root", BindingFlags.Public | BindingFlags.Instance);
    }

    private List<Transform> GetDynamicBoneRoots(Transform implantRoot)
    {
        List<Transform> roots = new List<Transform>();
        if (implantRoot == null)
            return roots;

        if (dynamicBoneBindMode == DynamicBoneBindMode.ImplantRoots)
        {
            roots.Add(implantRoot);
            return roots;
        }

        for (int i = 0; i < implantRoot.childCount; i++)
        {
            Transform child = implantRoot.GetChild(i);
            if (child != null)
                roots.Add(child);
        }

        return roots;
    }

    private int CountDynamicRoots(Transform implantRoot)
    {
        return GetDynamicBoneRoots(implantRoot).Count;
    }

    private static bool HasExistingBoneImplantProcess(Type bipType, GameObject hostObject, Transform trfSrc)
    {
        return FindExistingBoneImplantProcess(bipType, hostObject, trfSrc) != null;
    }

    private static Component FindExistingBoneImplantProcess(Type bipType, GameObject hostObject, Transform trfSrc)
    {
        if (bipType == null || hostObject == null || trfSrc == null)
            return null;

        FieldInfo srcField = bipType.GetField("trfSrc", BindingFlags.Public | BindingFlags.Instance);
        if (srcField == null)
            return null;

        Component[] components = hostObject.GetComponents(bipType);
        foreach (Component component in components)
        {
            if (component == null)
                continue;

            Transform existingSrc = srcField.GetValue(component) as Transform;
            if (existingSrc == trfSrc)
                return component;
        }

        return null;
    }

    private static HashSet<Transform> CollectSkinnedBones(GameObject root)
    {
        HashSet<Transform> bones = new HashSet<Transform>();
        SkinnedMeshRenderer[] renderers = root.GetComponentsInChildren<SkinnedMeshRenderer>(true);

        foreach (SkinnedMeshRenderer renderer in renderers)
        {
            if (renderer == null || renderer.bones == null)
                continue;

            foreach (Transform bone in renderer.bones)
            {
                if (bone != null)
                    bones.Add(bone);
            }
        }

        return bones;
    }

    private static bool HasBoneEvidence(Transform root, HashSet<Transform> skinnedBones)
    {
        if (skinnedBones.Contains(root))
            return true;

        Transform[] descendants = root.GetComponentsInChildren<Transform>(true);
        foreach (Transform descendant in descendants)
        {
            if (skinnedBones.Contains(descendant))
                return true;
        }

        return false;
    }

    private static string[] ParsePrefixes(string raw)
    {
        if (string.IsNullOrEmpty(raw))
            return new string[0];

        string[] split = raw.Split(new[] { ',', ';', '\n', '\r', '\t', ' ' }, StringSplitOptions.RemoveEmptyEntries);
        List<string> prefixes = new List<string>();

        foreach (string item in split)
        {
            string prefix = item.Trim();
            if (prefix.Length > 0)
                prefixes.Add(prefix);
        }

        return prefixes.ToArray();
    }

    private static bool HasAnyPrefix(string name, string[] prefixes)
    {
        if (prefixes == null || prefixes.Length == 0)
            return false;

        foreach (string prefix in prefixes)
        {
            if (name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    private static bool IsVanillaBoneName(string name)
    {
        if (string.IsNullOrEmpty(name))
            return false;

        return VanillaBones.Contains(name);
    }

    private static Type FindTypeByName(string typeName)
    {
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            Type[] types;
            try
            {
                types = assembly.GetTypes();
            }
            catch (ReflectionTypeLoadException ex)
            {
                types = ex.Types;
            }

            foreach (Type type in types)
            {
                if (type != null && type.Name == typeName)
                    return type;
            }
        }

        return null;
    }

    private class ImplantCandidate
    {
        public Transform Source;
        public Transform Destination;
        public bool HasSkinnedBoneEvidence;
        public bool HasExistingComponent;
    }

    private class HairDynamicBoneCandidate
    {
        public Transform Root;
        public Transform NearestRoot;
        public int Level;
        public string SourceLabel;
        public bool HasSkinnedBoneEvidence;
        public bool HasExistingDynamicBone;
    }

    private struct DynamicBoneApplyResult
    {
        public int AddedOrUpdated;
        public int Skipped;
        public int Failed;
    }
}
