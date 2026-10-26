import {describe,expect,it} from "vitest";
import {blankShot,moveShot,removeShot,resizeShot,sequence,splitShot,syncDuration} from "./storyboard-draft";
import type {CreativeStoryboard} from "@/lib/types";

function fixture():CreativeStoryboard {
  return {schema_version:"storyboard_v1",direction_id:"evidence-led",duration_ms:30000,fps:30,
    shots:sequence([blankShot(12000,"first"),blankShot(18000,"second")])};
}
function validTiming(board:CreativeStoryboard) {
  expect(board.shots[0].start_ms).toBe(0);
  expect(new Set(board.shots.map((shot)=>shot.id)).size).toBe(board.shots.length);
  for(let i=1;i<board.shots.length;i++)expect(board.shots[i].start_ms).toBe(board.shots[i-1].start_ms+board.shots[i-1].duration_ms);
  expect(board.shots.at(-1)!.start_ms+board.shots.at(-1)!.duration_ms).toBe(board.duration_ms);
  expect(board.shots.every((shot)=>shot.duration_ms>0)).toBe(true);
}

describe("storyboard draft timing",()=>{
  it("rebalances adjacent shots without changing total duration",()=>{
    const original=fixture();const changed=resizeShot(original,0,17000);
    expect(changed.shots.map((shot)=>shot.duration_ms)).toEqual([17000,13000]);
    expect(original.shots.map((shot)=>shot.duration_ms)).toEqual([12000,18000]);
    validTiming(changed);
    expect(resizeShot(changed,0,30000)).toBe(changed);
  });
  it("splits, moves and removes shots while retaining unique IDs and contiguity",()=>{
    const split=splitShot(fixture(),0,"third");validTiming(split);
    expect(split.shots.map((shot)=>shot.duration_ms)).toEqual([6000,6000,18000]);
    const moved=moveShot(split,1,1);validTiming(moved);
    expect(moved.shots.map((shot)=>shot.id)).toEqual(["first","second","third"]);
    const removed=removeShot(moved,1);validTiming(removed);
    expect(removed.shots.map((shot)=>shot.duration_ms)).toEqual([24000,6000]);
  });
  it("adapts to a changed brief only when the remaining shot stays positive",()=>{
    const original=fixture();const longer=syncDuration(original,36000,24);
    validTiming(longer);expect(longer.fps).toBe(24);
    expect(longer.shots.at(-1)!.duration_ms).toBe(24000);
    expect(syncDuration(original,12000,30)).toBe(original);
  });
});
