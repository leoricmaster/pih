"""人工核实 CLI 端到端测试（S1.3.2）。

需 docker compose up（postgres）。验：
  - pih verify list 输出 ready_for_manual 队列
  - pih verify confirm <id> → single_source → confirmed + verification_log
  - pih verify refute <id> --reason=... → refuted + reason 入库
  - 无 reason refute 拒绝（exit 2）
  - 不存在/非 single_source 的 confirm 拒绝（exit 1）
"""
from __future__ import annotations

import pytest
from _factory import seed_event
from conftest import q as _q

from pih.cli import main
from pih.envs import load_env

load_env()

pytestmark = pytest.mark.integration



class TestVerifyList:
    def test_list_shows_ready_for_manual_events(self, capsys):
        """verify list：列出 ready_for_manual=TRUE 的事件。"""
        seed_event(subject="三一", event_type="新品发布")
        seed_event(subject="徐工", event_type="财报", ready_for_manual=False)
        seed_event(subject="柳工", event_type="中标落地")

        code = main(["verify", "list"])
        out = capsys.readouterr().out
        assert code == 0
        assert "待人工核实事件：2 条" in out  # 三一 + 柳工（徐工 ready=False 不列）
        assert "三一" in out
        assert "柳工" in out
        assert "徐工" not in out
        assert "单源确认" in out  # 中文状态标签

    def test_list_empty_shows_hint(self, capsys):
        """无 ready_for_manual 事件时显示提示。"""
        code = main(["verify", "list"])
        out = capsys.readouterr().out
        assert code == 0
        assert "0 条" in out
        assert "无已具备升级条件" in out


class TestVerifyConfirm:
    def test_confirm_advances_single_source_to_confirmed(self, capsys):
        """confirm：single_source → confirmed + 写 log + 清 ready_for_manual。"""
        event_id = seed_event(status="single_source")

        code = main(["verify", "confirm", str(event_id)])
        out = capsys.readouterr().out
        assert code == 0
        assert "多源确认" in out

        rows = _q(
            "SELECT status, ready_for_manual FROM event WHERE id = %s", (event_id,)
        )
        assert rows[0] == ("confirmed", False)

        logs = _q(
            "SELECT from_status, to_status, operator FROM verification_log "
            "WHERE event_id = %s ORDER BY created_at DESC LIMIT 1",
            (event_id,),
        )
        assert logs[0] == ("single_source", "confirmed", "operator")

    def test_confirm_pending_event_rejected(self, capsys):
        """pending 状态的事件不能直接 confirm（仅 single_source 可确认）。"""
        event_id = seed_event(status="pending", ready_for_manual=True)

        code = main(["verify", "confirm", str(event_id)])
        err = capsys.readouterr().err
        assert code == 1  # EXIT_FAILED
        assert "不在 single_source 状态" in err

    def test_confirm_nonexistent_event_rejected(self, capsys):
        """不存在的 event_id 拒绝。"""
        code = main(["verify", "confirm", "99999"])
        err = capsys.readouterr().err
        assert code == 1
        assert "99999" in err


class TestVerifyRefute:
    def test_refute_with_reason_advances_to_refuted(self, capsys):
        """refute --reason：pending/single_source → refuted + reason 入库。"""
        event_id = seed_event(status="single_source")

        code = main([
            "verify", "refute", str(event_id), "--reason=主体误读，实为栏目名"
        ])
        out = capsys.readouterr().out
        assert code == 0
        assert "已证伪" in out

        rows = _q(
            "SELECT status, ready_for_manual FROM event WHERE id = %s", (event_id,)
        )
        assert rows[0] == ("refuted", False)

        logs = _q(
            "SELECT from_status, to_status, reason FROM verification_log "
            "WHERE event_id = %s ORDER BY created_at DESC LIMIT 1",
            (event_id,),
        )
        assert logs[0] == ("single_source", "refuted", "主体误读，实为栏目名")

    def test_refute_without_reason_rejected(self, capsys):
        """无 reason 的 refute 被 argparse 拒绝（exit 2）。"""
        event_id = seed_event()
        with pytest.raises(SystemExit) as exc:
            main(["verify", "refute", str(event_id)])
        assert exc.value.code == 2  # argparse required 参数缺失

    def test_refute_empty_reason_rejected(self, capsys):
        """空 reason 被业务层拒绝（exit 2）。"""
        event_id = seed_event()
        code = main(["verify", "refute", str(event_id), "--reason=   "])
        err = capsys.readouterr().err
        assert code == 2
        assert "必须填写理由" in err

    def test_refute_already_confirmed_rejected(self, capsys):
        """已 confirmed 的事件不能证伪（终态不可逆）。"""
        event_id = seed_event(status="confirmed", ready_for_manual=False)
        code = main([
            "verify", "refute", str(event_id), "--reason=测试"
        ])
        err = capsys.readouterr().err
        assert code == 1
        assert "已是终态" in err
