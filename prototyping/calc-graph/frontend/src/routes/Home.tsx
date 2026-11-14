import { Link } from "react-router-dom";
import { InfoTip } from "../help/InfoTip";

export function Home() {
  return (
    <div className="page">
      <h1>
        Calc Graph <InfoTip id="page.home" />
      </h1>
      <p className="page-lede">
        Links a structural model, its drawings and its calc package, keeps the evidence for every link, and shows which calcs go stale when an
        element changes.
      </p>
      <div className="home-cards">
        <article className="home-card">
          <h2>
            Synthetic IFC app <InfoTip id="home.ifc" />
          </h2>
          <p>3D model, load-path graph, element to calc links with evidence, and the impact of a change.</p>
          <Link className="btn primary" to="/ifc">Open</Link>
        </article>
        <article className="home-card">
          <h2>
            Drawing-set view <InfoTip id="home.set" />
          </h2>
          <p>Elements read off the plans, calc records, connections and findings, each opening the original page.</p>
          <Link className="btn primary" to="/set">Open</Link>
        </article>
        <article className="home-card">
          <h2>
            Move a column <InfoTip id="home.v2" />
          </h2>
          <p>Move or remove a column in the synthetic v2 building and see the calcs to redo and the potential change order.</p>
          <Link className="btn primary" to="/v2">Open</Link>
        </article>
      </div>
    </div>
  );
}
