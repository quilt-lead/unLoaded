import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import type {Sel} from './model';

export function EtabsEvidence({revision,selected,onSelect}:{revision?:number;selected:Sel;onSelect:(s:Sel,focus?:boolean)=>void}){
 const [search,setSearch]=useState('');
 const query=useQuery({queryKey:['review','records'],queryFn:async()=>{const r=await fetch('/api/review/1/records');if(!r.ok)throw Error('Could not load imported ETABS results');return r.json();}});
 const packet=query.data?.find((p:any)=>p.kind==='etabs_import'&&p.model_revision===revision);
 if(query.error)return <p role="alert">Could not load imported ETABS results.</p>;
 if(!packet)return null;
 const match=selected?.kind==='el'?packet.members.find((m:any)=>m.member_id===selected.id):null;
 const result=match?.result;
 const display=(v:any)=>v===null||v===undefined||v===''?'Not supplied':String(v);
 return <section style={{borderBottom:'1px solid var(--line)',paddingBottom:14,marginBottom:14}}>
  <h3 className="ifc-h3">ETABS imported results</h3>
  <p className="muted">{packet.program[0]?.ProgramName} {packet.program[0]?.Version} · AISC 360-10 · saved export, not a rerun</p>
  {result?<>
   <b>{result.Label} · {result.Story} · {result['Design Section']}</b>
   <dl className="ifc-kv">
    {['PMM Ratio','PMM Combo','P Ratio','M Major Ratio','M Minor Ratio','V Major Ratio','V Major Combo','V Minor Ratio','V Minor Combo','Status','Message'].map(k=><div key={k} style={{display:'contents'}}><dt>{k}</dt><dd>{display(result[k])}</dd></div>)}
   </dl>
   <p className="muted">Ratios are dimensionless. Preserve the exported status and warning when reviewing this member.</p>
   {match.notes.map((n:string)=><p className="bad" key={n}>{n}</p>)}
   <details><summary>Source and match evidence</summary><p>{match.match}</p><p>ETABS unique name: {result.UniqueName}</p><p>{packet.result_sheet}, row {result._row}</p><p>{match.connectivity_sheet}, row {match.connectivity_row}</p><p>Analysis section: {match.assignment['Analysis Section']}; exported length: {match.assignment.Length} in.</p></details>
  </>:<>
   <p>{packet.members.length} / {packet.result_rows} steel results linked by exact GUID. {packet.unmatched.length} unmatched.</p>
   {selected?.kind==='el'&&<p>No steel design summary row is linked to this selected element.</p>}
   <label>Find ETABS member<input className="ifc-select" style={{width:'100%'}} value={search} placeholder="Label or story, e.g. B1" onChange={e=>setSearch(e.target.value)}/></label>
   <div className="ifc-elist">{packet.members.filter((m:any)=>`${m.result.Label} ${m.result.Story}`.toLowerCase().includes(search.toLowerCase())).slice(0,12).map((m:any)=><button key={m.member_id} onClick={()=>onSelect({kind:'el',id:m.member_id},true)}><span>{m.result.Label} · {m.result.Story}</span><span>PMM {display(m.result['PMM Ratio'])}</span></button>)}</div>
  </>}
  <div className="ifc-acts">{packet.sources.map((s:any)=><a className="btn sm" key={s.sha256} href={s.url}>{s.name}</a>)}</div>
 </section>;
}
