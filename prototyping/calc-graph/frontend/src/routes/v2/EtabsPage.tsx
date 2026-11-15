import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { Panel } from "../../components/Panel";
import { EtabsPanel } from "./EtabsPanel";

/** /v2/etabs - the analysis-software link on its own page (no move: base model objects, .e2k export). */
export default function EtabsPage() {
  return (
    <div className="v2-page">
      <div className="v2-crumbs">
        <Link to="/v2">Move a column</Link> <span aria-hidden="true">/</span> ETABS
      </div>
      <h1 className="v2-title">
        ETABS link <InfoTip id="page.v2-etabs" />
      </h1>
      <p className="page-lede">
        Saved real ETABS runs of the current design (labelled with the ETABS version and date, with the agreement against our PyNite frames), then the
        synthetic building as ETABS would hold it (mock): stories, frames, points, sections, combos, design ratios and drifts. To send a change, move a
        column on the Move page and use the ETABS tab there.
      </p>
      <Panel title="ETABS model" info="panel.etabs" scroll={false}>
        <EtabsPanel move={null} />
      </Panel>
    </div>
  );
}
