import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/core/utils/numbers";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

const MODE_INFO = {
    customer: {
        icon: "person",
        help: _t("Every live bank is listed and the customer picks one."),
    },
    weighted: {
        icon: "balance",
        help: _t("Each payment goes to the bank furthest below its share, so the shares follow the weights all day."),
    },
    rotation: {
        icon: "autorenew",
        help: _t("The banks take turns in their order, each for its batch of consecutive payments."),
    },
    priority: {
        icon: "format_list_numbered",
        help: _t("The first bank takes every payment; the next one steps in when it is paused or full."),
    },
};

const BLOCKED_LABELS = {
    paused: _t("Paused after failures"),
    count_limit: _t("Daily payments limit reached"),
    amount_limit: _t("Daily amount limit reached"),
};

export class VestaControlCenter extends Component {
    static template = "vesta_payment.ControlCenter";

    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.periods = [
            { key: "today", label: _t("Today") },
            { key: "week", label: _t("7 days") },
            { key: "month", label: _t("30 days") },
        ];
        this.state = proxy({ data: null, period: "today", busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("vesta.payment.bank", "get_control_center", [this.state.period]);
    }

    // ------------------------------------------------------------------
    // Getters
    // ------------------------------------------------------------------

    get data() {
        return this.state.data;
    }

    get modes() {
        return this.data.modes.map((mode) => ({ ...mode, ...MODE_INFO[mode.key] }));
    }

    get installedBanks() {
        return this.data.banks.filter((bank) => bank.provider_id);
    }

    get otherBanks() {
        return this.data.banks.filter((bank) => !bank.provider_id);
    }

    get isAutomatic() {
        return this.data.mode !== "customer";
    }

    /** Slices of the distribution donut: the period's payments per bank. */
    get distribution() {
        const banks = this.installedBanks.filter((bank) => bank.attempts);
        const total = banks.reduce((sum, bank) => sum + bank.attempts, 0);
        let start = 0;
        const slices = banks.map((bank) => {
            const share = total ? (100 * bank.attempts) / total : 0;
            const slice = { ...bank, share, start, end: start + share };
            start += share;
            return slice;
        });
        return { total, slices };
    }

    get donutStyle() {
        const { slices } = this.distribution;
        if (!slices.length) {
            return "background: var(--vesta-cc-track);";
        }
        const stops = slices.map((s) => `${s.color} ${s.start}% ${s.end}%`).join(", ");
        return `background: conic-gradient(${stops});`;
    }

    get timelineMax() {
        return Math.max(1, ...this.data.timeline.map((bucket) => this.bucketTotal(bucket)));
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    bankByCode(code) {
        return this.data.banks.find((bank) => bank.code === code);
    }

    bucketTotal(bucket) {
        return Object.values(bucket.counts).reduce((sum, count) => sum + count, 0);
    }

    barStyle(bucket) {
        return `height: ${(100 * this.bucketTotal(bucket)) / this.timelineMax}%;`;
    }

    shareStyle(value, color) {
        return `width: ${Math.min(value || 0, 100)}%; background: ${color};`;
    }

    number(value) {
        return formatFloat(value || 0, { digits: [false, 0] });
    }

    rial(value) {
        return `${this.number(value)} ${_t("Rial")}`;
    }

    stateLabel(bank) {
        return {
            live: _t("Live"),
            test: _t("Test Mode"),
            disabled: _t("Disabled"),
            uninstalled: _t("Not Installed"),
            missing: _t("Pro"),
        }[bank.state];
    }

    blockedLabel(bank) {
        return BLOCKED_LABELS[bank.blocked] || "";
    }

    // ------------------------------------------------------------------
    // Handlers
    // ------------------------------------------------------------------

    async run(callback) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await callback();
            await this.load();
        } finally {
            this.state.busy = false;
        }
    }

    async setPeriod(period) {
        this.state.period = period;
        await this.load();
    }

    setMode(mode) {
        return this.run(() => this.orm.call("vesta.payment.bank", "set_routing", [mode, this.data.show_all]));
    }

    toggleShowAll(ev) {
        const showAll = ev.target.checked;
        return this.run(() => this.orm.call("vesta.payment.bank", "set_routing", [this.data.mode, showAll]));
    }

    updateBank(bank, key, ev) {
        const value = Math.max(0, parseInt(ev.target.value || "0", 10) || 0);
        return this.run(() => this.orm.call("vesta.payment.bank", "update_bank", [[bank.id], { [key]: value }]));
    }

    moveBank(bank, direction) {
        return this.run(() => this.orm.call("vesta.payment.bank", "move_bank", [[bank.id], direction]));
    }

    bankAction(bank, action) {
        return this.run(async () => {
            const result = await this.orm.call("vesta.payment.bank", "run_bank_action", [[bank.id], action]);
            this.notification.add(result.message, { title: result.title, type: result.type });
        });
    }

    installBank(bank) {
        return this.run(async () => {
            const action = await this.orm.call("vesta.payment.bank", "action_install", [[bank.id]]);
            await this.action.doAction(action);
        });
    }

    openBank(bank) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "payment.provider",
            res_id: bank.provider_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPayments(bank) {
        return this.orm.call("vesta.payment.bank", "action_view_transactions", [[bank.id]]).then((action) => this.action.doAction(action));
    }

    openAllPayments() {
        this.action.doAction("vesta_payment.action_vesta_payment_transaction");
    }
}

registry.category("actions").add("vesta_payment.control_center", VestaControlCenter);
