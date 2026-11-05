"""Opt-in, single-contract hypothetical execution ledger; never sends orders."""
import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path


def number(value, name, minimum=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name}: finite number required')
    if (minimum is not None and value < minimum) or (positive and value <= 0):
        raise ValueError(f'{name}: out of range')
    return float(value)


def stamp(value, name):
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name}: ISO timestamp required') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f'{name}: timezone required')
    return result


def replay(payload):
    """Cash includes realized P&L minus fees; equity adds marked open P&L."""
    try:
        capital = number(payload['initial_capital'], 'initial_capital', positive=True)
        fee = number(payload['fee_per_lot'], 'fee_per_lot', minimum=0)
        slip = number(payload['slippage'], 'slippage', minimum=0)
        rows = payload['rows']
    except (KeyError, TypeError) as exc:
        raise ValueError('Missing configuration field') from exc
    if not isinstance(rows, list) or not rows:
        raise ValueError('rows: nonempty list required')
    cash, position, basis, realized_total, fees_total = capital, 0, 0., 0., 0.
    contract = multiplier = previous_close_at = None
    ledger, assumptions = [], set()
    for index, source in enumerate(rows):
        try:
            row_contract = source['contract']
            if not isinstance(row_contract, str) or not row_contract.strip():
                raise ValueError('contract required')
            if contract is not None and contract != row_contract:
                raise ValueError('Contract switching is not supported; supply one contract')
            contract = row_contract
            decision = stamp(source['decision_at'], 'decision_at')
            opened = stamp(source['open_at'], 'open_at')
            closed = stamp(source['close_at'], 'close_at')
            target_time = stamp(source['target_at'], 'target_at')
            if not target_time <= decision < opened < closed:
                raise ValueError('Require target_at <= decision_at < open_at < close_at')
            if previous_close_at is not None and not previous_close_at < decision:
                raise ValueError('Rows must be chronological and nonoverlapping')
            previous_close_at = closed
            for field in ('rule_available_at', 'capacity_available_at'):
                if source.get(field) is None:
                    assumptions.add(field + ': unproven historical availability')
                elif stamp(source[field], field) > decision:
                    raise ValueError(field + ': future information')
            opening = number(source['open'], 'open', positive=True)
            closing = number(source['close'], 'close', positive=True)
            lower = number(source['lower_limit'], 'lower_limit', minimum=0)
            upper = number(source['upper_limit'], 'upper_limit', positive=True)
            if not lower < upper or not lower <= opening <= upper or not lower <= closing <= upper:
                raise ValueError('Invalid limits or prices outside limits')
            mult = number(source['multiplier'], 'multiplier', positive=True)
            if multiplier is not None and multiplier != mult:
                raise ValueError('Contract multiplier cannot change within a run')
            multiplier = mult
            margin = number(source['margin_rate'], 'margin_rate', positive=True)
            if margin > 1:
                raise ValueError('margin_rate must be <= 1')
            target = math.trunc(number(source['target_lots'], 'target_lots'))
            capacity = source['capacity_lots']
            if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
                raise ValueError('capacity_lots: nonnegative integer required')
        except (KeyError, TypeError) as exc:
            raise ValueError(f'row {index}: missing or malformed field') from exc

        before = position
        equity_open = cash + position * (opening - basis) * mult
        breach_open = equity_open < abs(position) * opening * mult * margin
        requested = target - position
        direction = 1 if requested > 0 else -1
        fill_price = opening + direction * slip
        events = ['margin_breach_at_open'] if breach_open else []
        row_fees = row_realized = 0.
        filled = 0
        if requested:
            blocked = fill_price <= 0 or (direction > 0 and opening >= upper) or (direction < 0 and opening <= lower) or not lower <= fill_price <= upper
            if blocked:
                events.append('limit_blocked')
            else:
                quantity = min(abs(requested), capacity)
                if quantity < abs(requested):
                    events.append('capacity_limited')
                closing_lots = min(abs(position), quantity) if position * direction < 0 else 0
                if closing_lots:
                    row_realized = closing_lots * (1 if position > 0 else -1) * (fill_price - basis) * mult
                    cash += row_realized - closing_lots * fee
                    row_fees += closing_lots * fee
                    position += direction * closing_lots
                    filled += direction * closing_lots
                    if not position:
                        basis = 0.
                wanted_open = quantity - closing_lots
                if wanted_open:
                    if breach_open:
                        events.append('margin_breach_no_new_open')
                        allowed = 0
                    else:
                        equity_now = cash + position * (opening - basis) * mult
                        # Reserve margin conservatively using the higher of fill and mark.
                        margin_price = max(opening, fill_price)
                        free = equity_now - abs(position) * margin_price * mult * margin
                        unit = margin_price * mult * margin + fee + slip * mult
                        allowed = max(0, math.floor(free / unit))
                    opening_lots = min(wanted_open, allowed)
                    if opening_lots < wanted_open:
                        events.append('margin_limited')
                    if opening_lots:
                        basis = (abs(position) * basis + opening_lots * fill_price) / (abs(position) + opening_lots)
                        position += direction * opening_lots
                        cash -= opening_lots * fee
                        row_fees += opening_lots * fee
                        filled += direction * opening_lots
        fees_total += row_fees
        realized_total += row_realized
        unrealized = position * (closing - basis) * mult
        equity = cash + unrealized
        required_margin = abs(position) * closing * mult * margin
        breached = equity < required_margin
        if breached:
            events.append('margin_breach_at_close')
        if not all(math.isfinite(v) for v in (cash, equity, required_margin, realized_total, fees_total)):
            raise ValueError('Numerical overflow in ledger')
        ledger.append(dict(open_at=source['open_at'], close_at=source['close_at'], contract=contract,
            target_lots=target, previous_position=before, position=position, filled_delta=filled,
            fill_price=fill_price if filled else None, fees=row_fees, total_fees=fees_total,
            realized_pnl=realized_total, unrealized_pnl=unrealized, cash=cash, equity=equity,
            required_margin=required_margin, margin_breach=breached,
            margin_breach_at_open=breach_open, events=events))
    return dict(mode='hypothetical_constraints', executable=False,
        evidence_status='assumption_only' if assumptions else 'timestamps_supplied_not_independently_verified',
        assumptions=sorted(assumptions), initial_capital=capital, final_equity=ledger[-1]['equity'],
        total_fees=fees_total, open_position=position, ledger=ledger)


def main():
    parser = argparse.ArgumentParser(description='单合约成交约束情景回放，不连接交易账户')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('输出目录已存在，请换一个新目录')
        result = replay(json.loads(args.input.read_text(encoding='utf-8')))
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        with (args.output / 'ledger.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result['ledger'][0]))
            writer.writeheader()
            writer.writerows({**row, 'events': '|'.join(row['events'])} for row in result['ledger'])
        (args.output / '使用结果.md').write_text(
            '# 成交约束情景回放\n\n'
            '这是单合约假设账本，不是真实成交认证，也不改变原有回测结果。\n\n'
            f"- 初始资金：{result['initial_capital']:.2f}\n- 期末权益：{result['final_equity']:.2f}\n"
            f"- 累计手续费：{result['total_fees']:.2f}\n- 期末未平仓手数：{result['open_position']}\n\n"
            '未平仓不会被假装平掉；保证金不足只报警并限制开仓，不模拟强平。'
            '手续费为每手单边固定金额，不支持平今差异；不支持换月、队列或逐笔撮合。'
            '历史规则时间及成交容量由输入提供，尚未独立认证。\n\n'
            '[逐日账本](ledger.csv) · [完整结果与证据状态](report.json)\n', encoding='utf-8')
    except (OSError, ValueError) as exc:
        parser.exit(2, f'未完成回放：{type(exc).__name__}。请检查输入规则、时间顺序和输出目录。\n')


if __name__ == '__main__':
    main()
