import type { ReactNode } from "react";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";
import { PdfPage, type PdfSource } from "./PdfPage";

export interface EvidenceCompareProps {
  left: PdfSource | null;
  right: PdfSource | null;
  leftTitle: ReactNode;
  rightTitle: ReactNode;
  /** help id for the comparison as a whole */
  info: HelpId;
  /** help id passed to both pages */
  pageInfo: HelpId;
  /** a line under the titles, e.g. what differs */
  note?: ReactNode;
}

/** Two original pages side by side (stacked on a phone), each zoomed to its own evidence. */
export function EvidenceCompare({ left, right, leftTitle, rightTitle, info, pageInfo, note }: EvidenceCompareProps) {
  return (
    <div className="cg-compare">
      <div className="cg-compare-head">
        <span className="cg-compare-title">
          Evidence side by side
          <InfoTip id={info} />
        </span>
        {note && <span className="cg-compare-note">{note}</span>}
      </div>
      <div className="cg-compare-cols">
        <div className="cg-compare-col">
          <div className="cg-compare-side">{leftTitle}</div>
          <PdfPage source={left} info={pageInfo} />
        </div>
        <div className="cg-compare-col">
          <div className="cg-compare-side">{rightTitle}</div>
          <PdfPage source={right} info={pageInfo} />
        </div>
      </div>
    </div>
  );
}
