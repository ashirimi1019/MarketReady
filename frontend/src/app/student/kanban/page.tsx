"use client";

import { useEffect, useState, useCallback } from "react";
import { DragDropContext, Droppable, Draggable, DropResult } from "@hello-pangea/dnd";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";
import Link from "next/link";

type Task = {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  week_number?: number | null;
  skill_tag?: string | null;
  priority: string;
  github_synced: boolean;
  ai_generated: boolean;
  sort_order: number;
};

type Board = { todo: Task[]; in_progress: Task[]; done: Task[] };
type BoardResponse = { board: Board; total: number };

const COL_META: Record<string, { label: string; color: string; bg: string }> = {
  todo: { label: "To Do", color: "#3d6dff", bg: "rgba(61,109,255,0.06)" },
  in_progress: { label: "In Progress", color: "#ffb300", bg: "rgba(255,179,0,0.06)" },
  done: { label: "Done", color: "#00c896", bg: "rgba(0,200,150,0.06)" },
};

const PRIORITY_COLOR: Record<string, string> = {
  high: "#ff3b30",
  medium: "#ffb300",
  low: "#00c896",
};

function TaskCard({ task, index }: { task: Task; index: number }) {
  return (
    <Draggable draggableId={task.id} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          data-testid={`task-card-${task.id}`}
          className="rounded-xl border border-[color:var(--border)] p-3 text-sm cursor-grab active:cursor-grabbing"
          style={{
            background: snapshot.isDragging ? "var(--surface-hi)" : "var(--surface)",
            boxShadow: snapshot.isDragging ? "0 8px 24px rgba(0,0,0,0.3)" : undefined,
            ...provided.draggableProps.style,
          }}
        >
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <p className="font-medium leading-snug">{task.title}</p>
            <span className="h-2 w-2 rounded-full flex-shrink-0 mt-1" style={{ background: PRIORITY_COLOR[task.priority] || "#7b8ab8" }} />
          </div>
          {task.description && <p className="text-xs text-[color:var(--muted)] mb-2 leading-relaxed line-clamp-2">{task.description}</p>}
          <div className="flex items-center gap-1.5 flex-wrap">
            {task.week_number != null && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[rgba(61,109,255,0.1)] text-[color:var(--primary)]">W{task.week_number}</span>
            )}
            {task.skill_tag && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[rgba(0,200,150,0.1)] text-[color:var(--success)]">{task.skill_tag}</span>
            )}
            {task.ai_generated && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[rgba(249,74,210,0.1)] text-[color:var(--accent-3)]">AI</span>
            )}
            {task.github_synced && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[rgba(0,200,150,0.08)] text-[color:var(--success)]">GitHub</span>
            )}
          </div>
        </div>
      )}
    </Draggable>
  );
}

function AddTaskForm({ colStatus, onAdd }: { colStatus: string; onAdd: (t: Task) => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!title.trim()) return;
    setLoading(true);
    try {
      const task = await apiSend<Task>("/kanban/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), status: colStatus, priority: "medium" }),
      });
      onAdd(task);
      setTitle("");
      setOpen(false);
    } catch {}
    setLoading(false);
  };

  if (!open) return (
    <button className="w-full text-left text-xs text-[color:var(--muted)] hover:text-[color:var(--foreground)] px-2 py-1.5 rounded-lg hover:bg-[rgba(61,109,255,0.06)] transition-colors" onClick={() => setOpen(true)} data-testid={`add-task-btn-${colStatus}`}>
      + Add task
    </button>
  );

  return (
    <div className="space-y-2">
      <input
        autoFocus
        value={title}
        onChange={e => setTitle(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") submit(); if (e.key === "Escape") setOpen(false); }}
        placeholder="Task title..."
        className="w-full text-sm rounded-lg border border-[color:var(--border)] bg-[color:var(--input-bg)] px-3 py-2 outline-none focus:border-[color:var(--primary)]"
        data-testid="add-task-input"
      />
      <div className="flex gap-2">
        <button className="cta cta-primary text-xs px-3 py-1.5" onClick={submit} disabled={loading} data-testid="add-task-confirm">
          {loading ? "..." : "Add"}
        </button>
        <button className="cta cta-secondary text-xs px-3 py-1.5" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  );
}

export default function KanbanPage() {
  const { isLoggedIn } = useSession();
  const [board, setBoard] = useState<Board>({ todo: [], in_progress: [], done: [] });
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [weekFilter, setWeekFilter] = useState<number | null>(null);
  const [msg, setMsg] = useState("");

  const loadBoard = useCallback(() => {
    setLoading(true);
    apiGet<BoardResponse>("/kanban/board")
      .then(data => setBoard(data.board))
      .catch(() => setBoard({ todo: [], in_progress: [], done: [] }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { if (isLoggedIn) loadBoard(); }, [isLoggedIn, loadBoard]);

  const filterTasks = (tasks: Task[]) =>
    weekFilter ? tasks.filter(t => t.week_number === weekFilter) : tasks;

  const onDragEnd = async (result: DropResult) => {
    const { destination, source, draggableId } = result;
    if (!destination) return;
    if (destination.droppableId === source.droppableId && destination.index === source.index) return;

    const newBoard = { ...board };
    const srcCol = source.droppableId as keyof Board;
    const dstCol = destination.droppableId as keyof Board;
    const srcTasks = [...newBoard[srcCol]];
    const [moved] = srcTasks.splice(source.index, 1);
    newBoard[srcCol] = srcTasks;
    const dstTasks = [...newBoard[dstCol]];
    dstTasks.splice(destination.index, 0, { ...moved, status: dstCol });
    newBoard[dstCol] = dstTasks;
    setBoard(newBoard);

    await apiSend<Task>(`/kanban/tasks/${draggableId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: dstCol, sort_order: destination.index }),
    }).catch(() => loadBoard());
  };

  const generatePlan = async () => {
    setGenerating(true);
    setMsg("");
    try {
      const result = await apiSend<{ tasks_created: number; ai_powered: boolean }>("/kanban/generate", { method: "POST" });
      setMsg(`Generated ${result.tasks_created} tasks${result.ai_powered ? " (AI)" : " (template)"}`);
      loadBoard();
    } catch {
      setMsg("Error generating plan");
    }
    setGenerating(false);
  };

  const syncGithub = async () => {
    setSyncing(true);
    setMsg("");
    try {
      const result = await apiSend<{ synced_count: number }>("/kanban/sync-github", { method: "POST" });
      setMsg(`Synced ${result.synced_count} tasks from GitHub`);
      loadBoard();
    } catch (e: unknown) {
      const err = e as { message?: string };
      setMsg(err?.message === "GitHub username not set in profile" ? "Add your GitHub username in Profile first" : "GitHub sync error");
    }
    setSyncing(false);
  };

  const onTaskAdded = (task: Task, col: keyof Board) => {
    setBoard(prev => ({ ...prev, [col]: [...prev[col], task] }));
  };

  const weeks = Array.from(new Set([
    ...board.todo.map(t => t.week_number),
    ...board.in_progress.map(t => t.week_number),
    ...board.done.map(t => t.week_number),
  ].filter(Boolean))).sort((a, b) => (a as number) - (b as number)) as number[];

  if (!isLoggedIn) {
    return (
      <section className="panel text-center py-16">
        <p className="text-[color:var(--muted)]">Please log in to access your Kanban board.</p>
      </section>
    );
  }

  return (
    <section className="panel space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1">
          <h2 className="text-3xl font-bold tracking-tight" data-testid="kanban-title">90-Day Pivot Plan</h2>
          <p className="mt-1 text-[color:var(--muted)] text-sm">Drag tasks across columns to track your progress</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            className="cta cta-primary text-sm"
            onClick={generatePlan}
            disabled={generating}
            data-testid="generate-plan-btn"
          >
            {generating ? "Generating..." : "Generate AI Plan"}
          </button>
          <button
            className="cta cta-secondary text-sm"
            onClick={syncGithub}
            disabled={syncing}
            data-testid="github-sync-btn"
          >
            {syncing ? "Syncing..." : "GitHub Sync"}
          </button>
        </div>
      </div>

      {msg && (
        <div className="rounded-xl border border-[color:var(--border)] px-4 py-2 text-sm text-[color:var(--success)] bg-[rgba(0,200,150,0.06)]" data-testid="kanban-message">
          {msg}
        </div>
      )}

      {/* Week filter */}
      {weeks.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap" data-testid="week-filter">
          <span className="text-xs text-[color:var(--muted)]">Filter:</span>
          <button
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${!weekFilter ? "border-[color:var(--primary)] text-[color:var(--primary)] bg-[rgba(61,109,255,0.1)]" : "border-[color:var(--border)] text-[color:var(--muted)]"}`}
            onClick={() => setWeekFilter(null)}
          >All</button>
          {weeks.map(w => (
            <button key={w}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${weekFilter === w ? "border-[color:var(--primary)] text-[color:var(--primary)] bg-[rgba(61,109,255,0.1)]" : "border-[color:var(--border)] text-[color:var(--muted)]"}`}
              onClick={() => setWeekFilter(w === weekFilter ? null : w)}
            >Week {w}</button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 rounded-full border-2 border-[color:var(--primary)] border-t-transparent animate-spin" />
        </div>
      ) : (
        <DragDropContext onDragEnd={onDragEnd}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="kanban-board">
            {(["todo", "in_progress", "done"] as const).map(colId => {
              const meta = COL_META[colId];
              const tasks = filterTasks(board[colId]);
              return (
                <div key={colId} className="rounded-2xl border border-[color:var(--border)] overflow-hidden" data-testid={`kanban-col-${colId}`}>
                  <div className="px-4 py-3 border-b border-[color:var(--border)]" style={{ background: meta.bg }}>
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ background: meta.color }} />
                      <span className="text-sm font-semibold">{meta.label}</span>
                      <span className="ml-auto text-xs text-[color:var(--muted)] bg-[rgba(61,109,255,0.08)] px-2 py-0.5 rounded-full">
                        {board[colId].length}
                      </span>
                    </div>
                  </div>
                  <Droppable droppableId={colId}>
                    {(provided, snapshot) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.droppableProps}
                        className="min-h-32 p-3 space-y-2 transition-colors"
                        style={{ background: snapshot.isDraggingOver ? "rgba(61,109,255,0.04)" : "transparent" }}
                      >
                        {tasks.map((task, i) => (
                          <TaskCard key={task.id} task={task} index={i} />
                        ))}
                        {provided.placeholder}
                      </div>
                    )}
                  </Droppable>
                  <div className="px-3 pb-3">
                    <AddTaskForm colStatus={colId} onAdd={t => onTaskAdded(t, colId)} />
                  </div>
                </div>
              );
            })}
          </div>
        </DragDropContext>
      )}

      <div className="text-center">
        <Link href="/student/readiness" className="text-sm text-[color:var(--primary)] hover:opacity-80">
          View MRI Score to see what gaps to address first
        </Link>
      </div>
    </section>
  );
}
