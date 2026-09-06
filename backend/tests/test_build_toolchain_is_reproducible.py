"""构建工具链必须能被复现出来，否则「已固定版本」只是一句话。

``package.json`` 自己的 description 写着 "Install with `npm ci`"。而 v10.16.0 把
``tailwindcss`` 加进 devDependencies 时没有重新生成 ``package-lock.json`` ——
锁文件里一次 tailwindcss 都没出现过。于是：

    npm ci
    npm error `npm ci` can only install packages when your package.json and
    npm error package-lock.json are in sync.
    npm error Missing: tailwindcss@3.4.16 from lock file

``npm ci`` 一失败，``backend/scripts/build_cms.sh`` 就走它的两条退路：esbuild 用
机器上碰巧装着的全局版本（脚本自己会打印 "do not commit a bundle built with it"），
tailwind 用 ``npx --yes tailwindcss@3.4.16`` 现下载 —— 直接依赖是钉住的，它的
整棵传递依赖树不是。**「构建产物由固定版本决定」这句话因此在 v10.16.0 之后一直
不成立**，而且没有任何东西会说出来：脚本照常打印 "built 39913 bytes"。

（实测：用重新生成锁文件后的本地固定工具链重新编译，产物与线上那份逐字节相同，
所以 v10.16.0 发出去的字节没有问题。坏掉的是复现能力，不是那次产物。）

这条测试不跑 npm —— 发布机上可能没有网络，而且没必要。它只问一件事：
package.json 声明的每一个依赖，锁文件里都以同一个版本存在。
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_JSON = PROJECT_ROOT / "package.json"
LOCK_JSON = PROJECT_ROOT / "package-lock.json"


def _declared() -> dict[str, str]:
    manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    declared: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        declared.update(manifest.get(section) or {})
    return declared


def _locked_versions() -> dict[str, str]:
    """Every package the lock file pins, by name.

    npm lockfileVersion 2/3 keys packages by install path — ``node_modules/esbuild``,
    ``node_modules/@esbuild/darwin-arm64``. The leaf after the last ``node_modules/``
    is the package name, which is what package.json refers to.
    """

    lock = json.loads(LOCK_JSON.read_text(encoding="utf-8"))
    versions: dict[str, str] = {}
    for path, entry in (lock.get("packages") or {}).items():
        if not path or "node_modules/" not in path:
            continue
        name = path.split("node_modules/")[-1]
        version = entry.get("version")
        if version:
            versions[name] = version
    return versions


def test_every_pinned_build_tool_is_actually_in_the_lock_file() -> None:
    """`npm ci` 是唯一装出「发布固定版本」的方式；它必须真的能跑。

    少一个包，npm ci 整个失败——不是跳过那一个，是一个都不装。所以这里逐个断言，
    失败信息直接给出修法。
    """

    declared = _declared()
    locked = _locked_versions()

    missing = sorted(name for name in declared if name not in locked)
    assert not missing, (
        "package.json 声明了这些依赖，package-lock.json 里没有："
        f"{missing}。npm ci 会整体失败，构建脚本随后静默退回未固定的工具链。"
        "修法：npm install --package-lock-only，然后把锁文件一起提交。"
    )

    mismatched = {
        name: (want, locked[name])
        for name, want in declared.items()
        # 只比对精确钉住的版本；带 ^ ~ 的范围交给 npm 自己解。
        if name in locked and want[:1].isdigit() and locked[name] != want
    }
    assert not mismatched, (
        f"锁文件和 package.json 的版本对不上（包名: (声明, 锁定)）：{mismatched}"
    )


def test_the_build_scripts_only_fall_back_to_an_unpinned_toolchain_out_loud() -> None:
    """退路可以存在，但它必须自己喊出来——静默兜底就是缺陷本身。

    build_cms.sh 的 esbuild 退路会打印 WARNING；tailwind 的退路（npx --yes）在
    v10.16.0 里是完全无声的：它下载一个直接版本正确、传递依赖未固定的编译器，
    然后照常打印 "built 39913 bytes"。这条测试要求两条退路都能被操作者看见。
    """

    script = (PROJECT_ROOT / "backend" / "scripts" / "build_cms.sh").read_text(encoding="utf-8")
    tail = script[script.index("PINNED_TAILWIND="):]
    assert "npx --yes" in tail, "这条测试假设 tailwind 仍有一条 npx 网络退路；退路没了就重写它"
    fallback = tail[tail.index("npx --yes"):]
    # 退路那一支里必须有一句写给人看的警告，且要走 stderr（>&2），
    # 否则它会混进正常的 build 输出里没人看见。
    warn_window = tail[:tail.index("--minify")]
    assert ">&2" in warn_window and "WARNING" in warn_window.upper(), (
        "tailwind 落到 npx --yes 这条网络退路时没有任何警告：直接版本是钉住的，"
        "它的传递依赖不是，而产物字节由整棵树决定。请在退路分支里向 stderr 打印警告。"
    )
    assert fallback  # 退路本身仍在——我们要的是它出声，不是把它删掉
