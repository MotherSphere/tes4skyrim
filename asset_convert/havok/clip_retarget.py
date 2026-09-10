"""Retarget a decoded clip from one skeleton onto another.

World-space rotation retargeting: each source bone's rotation is expressed
as a deviation from a POSE of the source skeleton that matches the target's
rest pose (the per-bone delta matrices mined by
tools/generators/kf_animation_explorer.py), and that deviation is applied to
the target bone's rest rotation. Target bone lengths are kept, so the output
is a clip in the target's own bone order that the plain writer
(hkx_anim.write_clip_hkx) can compile unchanged.
See: docs/commentary/asset_convert_falloutnv.md#gun-animations

All 4x4 matrices are PyFFI's row-vector convention (v' = v @ M, translation
in row 4, world = local @ parent_world), the convention of every generated
skeleton JSON and of the delta cache.
"""

import json

import numpy as np

from asset_convert.havok.hkx_skeleton import Bone, find_skeleton_root
from asset_convert.havok.kf_decode import BoneTrack, DecodedClip
from asset_convert.nif.pyffi_monkey_patch import apply_patches
apply_patches()
from pyffi.formats.nif import NifFormat


def quat_wxyz_to_mat(q) -> np.ndarray:
    """Row-convention 3x3 for a (w, x, y, z) unit quaternion."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)],
        [2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)],
        [2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


def mat_to_quat_wxyz(m) -> np.ndarray:
    """Inverse of quat_wxyz_to_mat (Shepperd's method on the row matrix)."""
    m00, m01, m02 = m[0]
    m10, m11, m12 = m[1]
    m20, m21, m22 = m[2]
    trace = m00 + m11 + m22
    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2
        q = (0.25 * s, (m12 - m21) / s, (m20 - m02) / s, (m01 - m10) / s)
    elif m00 > m11 and m00 > m22:
        s = np.sqrt(1.0 + m00 - m11 - m22) * 2
        q = ((m12 - m21) / s, 0.25 * s, (m10 + m01) / s, (m20 + m02) / s)
    elif m11 > m22:
        s = np.sqrt(1.0 + m11 - m00 - m22) * 2
        q = ((m20 - m02) / s, (m10 + m01) / s, 0.25 * s, (m21 + m12) / s)
    else:
        s = np.sqrt(1.0 + m22 - m00 - m11) * 2
        q = ((m01 - m10) / s, (m20 + m02) / s, (m21 + m12) / s, 0.25 * s)
    q = np.array(q, dtype=np.float64)
    return q / np.linalg.norm(q)


def compose(translation, rot3, scale=1.0) -> np.ndarray:
    """Row-convention 4x4 from a translation, a 3x3 rotation and a scale."""
    m = np.eye(4)
    m[:3, :3] = np.asarray(rot3) * scale
    m[3, :3] = translation
    return m


class Skeleton:
    """Bone names, parents and rest transforms in one bone order."""

    def __init__(self, names, parents, local):
        self.names = list(names)
        self.parents = list(parents)
        self.local = np.asarray(local, dtype=np.float64)
        self.index = {n: i for i, n in enumerate(self.names)}
        self.world = self.fk(self.local)

    def fk(self, local) -> np.ndarray:
        """World matrices for per-bone locals (parents precede children)."""
        world = np.empty_like(local)
        for i, p in enumerate(self.parents):
            world[i] = local[i] if p < 0 else local[i] @ world[p]
        return world

    @classmethod
    def from_hkx_json(cls, path: str) -> 'Skeleton':
        """The hkx-order skeleton written by extract_skeleton_bones."""
        with open(path) as f:
            bones = json.load(f)['bones']
        local = [compose(b['translation'],
                         quat_wxyz_to_mat((b['quat_xyzw'][3],) +
                                          tuple(b['quat_xyzw'][:3])),
                         b['scale']) for b in bones]
        return cls([b['name'] for b in bones], [b['parent'] for b in bones],
                   local)

    @classmethod
    def from_nif(cls, path: str) -> 'Skeleton':
        """A NIF's NiNode bone tree, DFS order, AUTHORED names."""
        data = NifFormat.Data()
        with open(path, 'rb') as f:
            data.read(f)
        names, parents, local = [], [], []

        def visit(node, parent):
            idx = len(names)
            r = node.rotation
            rot = [[r.m_11, r.m_12, r.m_13], [r.m_21, r.m_22, r.m_23],
                   [r.m_31, r.m_32, r.m_33]]
            t = node.translation
            names.append(bytes(node.name).decode('latin-1').rstrip('\x00'))
            parents.append(parent)
            local.append(compose((t.x, t.y, t.z), rot, float(node.scale)))
            for child in node.children:
                if isinstance(child, NifFormat.NiNode):
                    visit(child, idx)

        visit(find_skeleton_root(data), -1)
        return cls(names, parents, local)

    def bones(self) -> list:
        """hkx_skeleton.Bone list (the writer's reference-pose input)."""
        out = []
        for i, name in enumerate(self.names):
            m = self.local[i]
            scale = float(np.linalg.norm(m[0, :3]))
            q = mat_to_quat_wxyz(m[:3, :3] / scale)
            out.append(Bone(name=name, parent=self.parents[i],
                            translation=tuple(float(v) for v in m[3, :3]),
                            quat_xyzw=(float(q[1]), float(q[2]),
                                       float(q[3]), float(q[0])),
                            scale=scale))
        return out


def load_pose_deltas(path: str) -> dict:
    """{bone: 4x4} from a best_animation_pose*.json delta cache."""
    with open(path) as f:
        raw = json.load(f)
    return {b: np.array(m, dtype=np.float64).reshape(4, 4)
            for b, m in raw.get('delta_matrices', {}).items()}


def posed_world(skel: Skeleton, deltas: dict) -> np.ndarray:
    """The source's matched pose: rest_world @ delta per bone."""
    world = skel.world.copy()
    for name, d in (deltas or {}).items():
        i = skel.index.get(name)
        if i is not None:
            world[i] = skel.world[i] @ d
    return world


def _source_locals(clip: DecodedClip, src: Skeleton, frame: int) -> np.ndarray:
    """Per-bone local matrices at `frame`, rest where a channel is absent.

    The root plays as identity: the accumulation child (`Bip01 NonAccum`)
    carries the body height and facing, so the NIF's rest root transform
    is never applied.
    See: docs/commentary/asset_convert_falloutnv.md#accum-root-identity
    """
    local = src.local.copy()
    for i, p in enumerate(src.parents):
        if p < 0:
            local[i] = np.eye(4)
    for tr in clip.tracks:
        i = src.index.get(tr.bone)
        if i is None:
            continue
        rest = src.local[i]
        scale = float(np.linalg.norm(rest[0, :3]))
        rot = (quat_wxyz_to_mat(tr.rotations[frame]) * scale
               if tr.rotations is not None else rest[:3, :3])
        t = (tr.translations[frame] if tr.translations is not None
             else rest[3, :3])
        local[i] = compose(t, rot / scale, scale)
    return local


#: Target bones that take the source's WORLD translation deviation (the
#: accumulation bone carrying body height); every other bone keeps its rest
#: offset, and the root stays at the origin like the source's.
TRANSLATED_BONES = ('NPC COM [COM ]',)
#: Bones whose mesh is authored in the SOURCE frame. See: docs/commentary/asset_convert_falloutnv.md#weapon-bone-verbatim
VERBATIM_BONES = ('Weapon',)


def fill_missing_tracks(clip: DecodedClip, base: DecodedClip) -> int:
    """Add `base`'s first-frame pose for every bone `clip` has no track for.

    A partial FNV clip is an overlay: the bones it leaves out hold the
    higher-priority clip (the aim pose), where a Havok clip would play the
    rest pose. Returns the number of tracks added.
    See: docs/commentary/asset_convert_falloutnv.md#first-person-rig
    """
    have = {t.bone for t in clip.tracks}
    n = len(clip.times)
    added = 0
    for tr in base.tracks:
        if tr.bone in have:
            continue
        clip.tracks.append(BoneTrack(
            bone=tr.bone,
            translations=(None if tr.translations is None
                          else np.tile(tr.translations[0], (n, 1))),
            rotations=(None if tr.rotations is None
                       else np.tile(tr.rotations[0], (n, 1)))))
        added += 1
    return added


def first_frame_pose(clip: DecodedClip, fps: float = 30.0) -> DecodedClip:
    """`clip`'s first frame as a looping two-frame pose clip with no keys.
    See: docs/commentary/asset_convert_falloutnv.md#level-aim-from-the-fire-clip
    """
    tracks = [BoneTrack(
        bone=tr.bone,
        translations=(None if tr.translations is None
                      else np.tile(tr.translations[0], (2, 1))),
        rotations=(None if tr.rotations is None
                   else np.tile(tr.rotations[0], (2, 1))))
        for tr in clip.tracks]
    return DecodedClip(name=clip.name, duration=1.0 / fps, cycle_type=0,
                       frequency=clip.frequency,
                       times=np.array([0.0, 1.0 / fps]), tracks=tracks)


def world_positions(clip: DecodedClip, skel: Skeleton, frame: int) -> np.ndarray:
    """World matrices of `skel` posed by `clip` (its own bone names)."""
    return skel.fk(_source_locals(clip, skel, frame))


def retarget_error(src_clip, dst_clip, src: Skeleton, dst: Skeleton,
                   bone_map: dict, bones, frame: int = 0) -> dict:
    """{source bone: world distance to its retargeted target} at `frame`.

    The offline retarget check: a mapped bone must land where the source
    skeleton put it, up to the two skeletons' own proportion differences.
    """
    sw = world_positions(src_clip, src, frame)
    dw = world_positions(dst_clip, dst, frame)
    out = {}
    for s in bones:
        d = bone_map.get(s)
        if s in src.index and d in dst.index:
            out[s] = float(np.linalg.norm(sw[src.index[s]][3, :3]
                                          - dw[dst.index[d]][3, :3]))
    return out


def _anchor_shift(src: Skeleton, dst: Skeleton, src_pose, mapped: dict,
                  anchor) -> dict:
    """{target bone index: constant} added to the translated bones' deviation.

    With an anchor (source bone, target bone) a translated bone lands at the
    target anchor's rest plus the source bone's offset from the source
    anchor, so camera-relative geometry survives rigs of different height;
    without one it keeps the target's own rest position.
    See: docs/commentary/asset_convert_falloutnv.md#first-person-rig
    """
    if anchor is None:
        return {}
    sa, da = src.world[src.index[anchor[0]]], dst.world[dst.index[anchor[1]]]
    return {di: (da[3, :3] - dst.world[di][3, :3] - sa[3, :3]
                 + src_pose[si][3, :3]) for di, si in mapped.items()}


def _pose_frame(rig: dict, src_world, rots, trans, f: int) -> None:
    """Write frame `f` of every mapped bone's local rotation/translation.

    See: docs/commentary/asset_convert_falloutnv.md#weapon-bone-verbatim
    """
    dst, mapped, shift = rig['dst'], rig['mapped'], rig['shift']
    src_pose, src_pose_rot_inv = rig['src_pose'], rig['src_pose_rot_inv']
    dst_world = np.empty_like(dst.world)
    for di, p in enumerate(dst.parents):
        rest = dst.local[di]
        parent_rot = np.eye(3) if p < 0 else dst_world[p][:3, :3]
        parent_t = np.zeros(3) if p < 0 else dst_world[p][3, :3]
        si = mapped.get(di)
        if si is None:
            rot = rest[:3, :3] @ parent_rot
        elif di in rig['verbatim']:
            rot = src_world[si][:3, :3]
        else:
            dev = src_pose_rot_inv[si] @ src_world[si][:3, :3]
            rot = dst.world[di][:3, :3] @ dev
        t = rest[3, :3] @ parent_rot + parent_t
        if di in rig['verbatim']:
            t = parent_t + src_world[si][3, :3] - src_world[
                rig['src_parents'][si]][3, :3]
        elif di in trans:
            t = t + (src_world[si][3, :3] - src_pose[si][3, :3]
                     + shift.get(di, 0.0))
        if di in trans:
            trans[di][f] = (t - parent_t) @ np.linalg.inv(parent_rot)
        dst_world[di] = compose(t, rot)
        if si is not None:
            rots[di][f] = mat_to_quat_wxyz(rot @ np.linalg.inv(parent_rot))


def retarget_clip(clip: DecodedClip, src: Skeleton, dst: Skeleton,
                  bone_map: dict, deltas: dict = None, name: str = None,
                  translated=TRANSLATED_BONES, anchor=None) -> DecodedClip:
    """`clip` (source bone names) as a clip over `dst`'s bones.

    bone_map: source bone -> target bone. Unmapped target bones and the
    root keep their rest local; the source's root-motion split must already
    have happened. `translated` names the target bones that take the
    source's world translation deviation; `anchor` (source bone, target
    bone) makes that deviation anchor-relative.
    See: docs/commentary/asset_convert_falloutnv.md#accum-root-identity
    """
    pairs = [(src.index[s], dst.index[d]) for s, d in bone_map.items()
             if s in src.index and d in dst.index
             and src.parents[src.index[s]] >= 0]
    src_pose = posed_world(src, deltas)
    mapped = {di: si for si, di in pairs}
    n_frames = len(clip.times)
    verbatim = {di for di in mapped if dst.names[di] in VERBATIM_BONES
                and src.parents[mapped[di]] >= 0}
    rots = {di: np.empty((n_frames, 4)) for di in mapped}
    trans = {di: np.empty((n_frames, 3)) for di in mapped
             if dst.names[di] in translated or di in verbatim}
    rig = {'dst': dst, 'mapped': mapped, 'src_pose': src_pose,
           'verbatim': verbatim, 'src_parents': src.parents,
           'src_pose_rot_inv': np.array([np.linalg.inv(w[:3, :3])
                                         for w in src_pose]),
           'shift': _anchor_shift(src, dst, src_pose,
                                  {di: mapped[di] for di in trans}, anchor)}
    for f in range(n_frames):
        _pose_frame(rig, src.fk(_source_locals(clip, src, f)), rots, trans, f)

    tracks = []
    for di in sorted(mapped):
        q = rots[di]
        for k in range(1, n_frames):          # keep one hemisphere
            if np.dot(q[k], q[k - 1]) < 0:
                q[k] = -q[k]
        tracks.append(BoneTrack(bone=dst.names[di], rotations=q,
                                translations=trans.get(di)))
    return DecodedClip(name=name or clip.name, duration=clip.duration,
                       cycle_type=clip.cycle_type, frequency=clip.frequency,
                       times=clip.times, tracks=tracks,
                       text_keys=list(clip.text_keys),
                       skipped_blocks=list(clip.skipped_blocks))
