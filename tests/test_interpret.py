from __future__ import annotations

import src.sti.__main__ as sti_main


def test_hello_world_prints(capfd, tmp_path, monkeypatch) -> None:
    program = """\
<-> Hello, Stream!

gyge stdout -:> <o>::fd::stdout;

season -:> spring;
drift -:> gentle;

spring -:> {
  "Hello, world!" -> stdout
}
"""
    prog_path = tmp_path / "hello.program"
    prog_path.write_text(program, encoding="utf-8")

    # Simulate: python -m sti hello.program
    monkeypatch.setattr("sys.argv", ["python -m sti", str(prog_path)])

    sti_main.main()

    out, err = capfd.readouterr()
    assert err == ""
    assert out.strip() == "Hello, world!"
