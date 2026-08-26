import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import UserPersonaSetup from "./UserPersonaSetup.jsx";

// 계약 출처: 1단계 API 명세서 §12, MBTI → Big Five 정책 문서(mbti-big-five-v0.1)
const students = [
  { id: "student-01", name: "아델", agent_type: "student", mbti_type: "ISTJ" },
  { id: "student-02", name: "레오", agent_type: "student", mbti_type: "ESTP" },
  { id: "student-03", name: "리아", agent_type: "student", mbti_type: "INFP" },
  { id: "student-04", name: "카이", agent_type: "student", mbti_type: "ENTJ" },
  { id: "student-05", name: "세라", agent_type: "student", mbti_type: "ESFJ" },
];

const configData = {
  rule_version: "mbti-big-five-v0.1",
  global_min: -50,
  global_max: 50,
  step: 5,
  mbti_rules: {
    ISTJ: {
      openness: { min: -45, default: -25, max: 5 },
      conscientiousness: { min: -15, default: 25, max: 45 },
      extraversion: { min: -45, default: -25, max: 5 },
      agreeableness: { min: -45, default: -20, max: 15 },
      emotional_stability: { min: -50, default: 0, max: 50 },
    },
    INFP: {
      openness: { min: -5, default: 25, max: 45 },
      conscientiousness: { min: -45, default: -25, max: 15 },
      extraversion: { min: -45, default: -25, max: 5 },
      agreeableness: { min: -15, default: 20, max: 45 },
      emotional_stability: { min: -50, default: 0, max: 50 },
    },
    ENTJ: {
      openness: { min: -5, default: 25, max: 45 },
      conscientiousness: { min: -15, default: 25, max: 45 },
      extraversion: { min: -5, default: 25, max: 45 },
      agreeableness: { min: -45, default: -20, max: 15 },
      emotional_stability: { min: -50, default: 0, max: 50 },
    },
    ESTP: {
      openness: { min: -45, default: -25, max: 5 },
      conscientiousness: { min: -45, default: -25, max: 15 },
      extraversion: { min: -5, default: 25, max: 45 },
      agreeableness: { min: -45, default: -20, max: 15 },
      emotional_stability: { min: -50, default: 0, max: 50 },
    },
    ESFJ: {
      openness: { min: -45, default: -25, max: 5 },
      conscientiousness: { min: -15, default: 25, max: 45 },
      extraversion: { min: -5, default: 25, max: 45 },
      agreeableness: { min: -15, default: 20, max: 45 },
      emotional_stability: { min: -50, default: 0, max: 50 },
    },
  },
};

function appliedPersona(overrides = {}) {
  return {
    agent_id: "student-03",
    simulation_id: "sim_01",
    agent_type: "USER_PERSONA",
    mbti_type: "INFP",
    openness: 25,
    conscientiousness: -25,
    extraversion: -25,
    agreeableness: 20,
    emotional_stability: 0,
    personality_rule_version: "mbti-big-five-v0.1",
    status: "APPLIED",
    locked: false,
    ...overrides,
  };
}

function response(body, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) });
}

// 초기 로드 시 GET config -> GET persona 순으로 호출된다.
function mockInitialLoad({ personaStatus = 404, personaBody = {} } = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementationOnce(() => response({ data: configData }))
    .mockImplementationOnce(() => response(personaBody, personaStatus));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("UserPersonaSetup", () => {
  it("Student 5명을 선택 옵션으로 표시한다", async () => {
    mockInitialLoad();
    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);

    for (const student of students) {
      expect(await screen.findByLabelText(student.name)).toBeInTheDocument();
    }
  });

  it("MBTI 선택 전에는 Big Five 조절 버튼이 비활성화된다", async () => {
    mockInitialLoad();
    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);
    await screen.findByLabelText(students[0].name);

    screen.getAllByRole("button", { name: /증가/ }).forEach((button) => expect(button).toBeDisabled());
    screen.getAllByRole("button", { name: /감소/ }).forEach((button) => expect(button).toBeDisabled());
  });

  it("MBTI를 선택하면 Big Five가 해당 MBTI 기본값으로 초기화된다", async () => {
    mockInitialLoad();
    const user = userEvent.setup();
    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);
    await screen.findByLabelText(students[0].name);

    await user.selectOptions(screen.getByLabelText("MBTI preset"), "INFP");

    // INFP 기본값: openness 25, conscientiousness -25, extraversion -25, agreeableness 20, emotional_stability 0
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getAllByText("-25")).toHaveLength(2);
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("MBTI를 다시 선택하면 기존 조절값을 버리고 새 기본값으로 초기화한다", async () => {
    mockInitialLoad();
    const user = userEvent.setup();
    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);
    await screen.findByLabelText(students[0].name);

    await user.selectOptions(screen.getByLabelText("MBTI preset"), "ISTJ");
    await user.click(screen.getByLabelText("성실성 증가")); // 25 -> 30

    await user.selectOptions(screen.getByLabelText("MBTI preset"), "ENTJ");

    // ENTJ conscientiousness 기본값은 25 (ISTJ에서 올린 30이 남아있으면 실패)
    expect(screen.queryByText("30")).not.toBeInTheDocument();
  });

  it("허용 범위 경계에 도달하면 해당 버튼이 비활성화된다", async () => {
    mockInitialLoad();
    const user = userEvent.setup();
    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);
    await screen.findByLabelText(students[0].name);

    await user.selectOptions(screen.getByLabelText("MBTI preset"), "INFP");

    // extraversion: min -45, default -25 -> 4번 감소하면 -45 경계 도달
    const decreaseExtraversion = screen.getByLabelText("외향성 감소");
    for (let i = 0; i < 4; i += 1) {
      await user.click(decreaseExtraversion);
    }
    expect(decreaseExtraversion).toBeDisabled();
  });

  it("시작 후(locked)에는 입력이 잠기고 저장 버튼이 사라진다", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => response({ data: configData }))
      .mockImplementationOnce(() => response({ data: appliedPersona({ locked: true }) }));

    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);

    expect(await screen.findByText(/Simulation이 시작되어/)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /Student 선택/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Persona 저장" })).not.toBeInTheDocument();
  });
  it("Persona를 저장해도 Simulation은 자동으로 시작되지 않는다", async () => {
    const fetchMock = mockInitialLoad();

    // POST /user-persona
    fetchMock.mockImplementationOnce(() =>
      response({ data: appliedPersona({ locked: false }) })
    );

    const onSaved = vi.fn();
    const user = userEvent.setup();

    render(
      <UserPersonaSetup
        simulationId="sim_01"
        students={students}
        token="t"
        onSaved={onSaved}
      />
    );

    await screen.findByLabelText(students[0].name);

    await user.click(screen.getByLabelText(students[2].name));
    await user.selectOptions(screen.getByLabelText("MBTI preset"), "INFP");
    await user.click(screen.getByRole("button", { name: "Persona 저장" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());

    // Persona 저장 요청만 나가고 start는 호출되지 않는다.
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const [personaUrl, personaOptions] = fetchMock.mock.calls[2];

    expect(personaUrl).toContain("/v1/simulations/sim_01/user-persona");
    expect(personaOptions.method).toBe("POST");
    expect(JSON.parse(personaOptions.body)).toEqual({
      agent_id: students[2].id,
      mbti_type: "INFP",
      personality_rule_version: "mbti-big-five-v0.1",
      openness: 25,
      conscientiousness: -25,
      extraversion: -25,
      agreeableness: 20,
      emotional_stability: 0,
    });

    // 저장 후에도 잠기지 않고, 저장/시작 버튼이 모두 남아있어야 한다.
    expect(screen.queryByText(/Simulation이 시작되어/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Persona 저장" })
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Simulation 시작" })
    ).toBeEnabled();
  });

  it("저장된 Persona로 Simulation 시작 버튼을 누르면 locked 상태로 입력을 잠근다", async () => {
    const fetchMock = mockInitialLoad();

    // POST /user-persona
    fetchMock.mockImplementationOnce(() =>
      response({ data: appliedPersona({ locked: false }) })
    );

    // POST /start
    fetchMock.mockImplementationOnce(() =>
      response({
        data: {
          id: "sim_01",
          status: "RUNNING",
          started_at: "2026-08-25T03:00:00Z",
        },
      })
    );

    const user = userEvent.setup();

    render(
      <UserPersonaSetup simulationId="sim_01" students={students} token="t" />
    );

    await screen.findByLabelText(students[0].name);

    await user.click(screen.getByLabelText(students[2].name));
    await user.selectOptions(screen.getByLabelText("MBTI preset"), "INFP");
    await user.click(screen.getByRole("button", { name: "Persona 저장" }));

    await screen.findByRole("button", { name: "Simulation 시작" });

    await user.click(screen.getByRole("button", { name: "Simulation 시작" }));

    await waitFor(() => {
      expect(screen.getByText(/Simulation이 시작되어/)).toBeInTheDocument();
    });

    // Simulation 시작 요청 확인
    const [startUrl, startOptions] = fetchMock.mock.calls[3];

    expect(startUrl).toContain("/v1/simulations/sim_01/start");
    expect(startOptions.method).toBe("POST");

    // Simulation 시작 후 입력이 잠겼는지 확인
    expect(
      screen.getByRole("group", { name: /Student 선택/ })
    ).toBeDisabled();
    expect(screen.getByLabelText("MBTI preset")).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Persona 저장" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Simulation 시작" })
    ).not.toBeInTheDocument();
  });

  it("아직 저장하지 않은 상태에서는 Simulation 시작 버튼이 비활성화된다", async () => {
    mockInitialLoad();
    const user = userEvent.setup();

    render(
      <UserPersonaSetup simulationId="sim_01" students={students} token="t" />
    );

    await screen.findByLabelText(students[0].name);
    await user.click(screen.getByLabelText(students[0].name));
    await user.selectOptions(screen.getByLabelText("MBTI preset"), "ISTJ");

    expect(screen.getByRole("button", { name: "Simulation 시작" })).toBeDisabled();
  });

  it("Simulation 시작이 409로 실패하면 서버 상태로 재동기화하고 잠긴다", async () => {
    const fetchMock = mockInitialLoad();

    // POST /user-persona
    fetchMock.mockImplementationOnce(() =>
      response({ data: appliedPersona({ locked: false }) })
    );

    // POST /start -> 409 (다른 경로로 이미 시작됨)
    fetchMock.mockImplementationOnce(() =>
      response(
        {
          code: "CONFLICT",
          message: "Simulation이 이미 시작되어 있습니다.",
        },
        409
      )
    );

    // 재동기화용 GET /user-persona -> 서버는 이미 locked 상태
    fetchMock.mockImplementationOnce(() =>
      response({ data: appliedPersona({ locked: true }) })
    );

    const user = userEvent.setup();

    render(
      <UserPersonaSetup simulationId="sim_01" students={students} token="t" />
    );

    await screen.findByLabelText(students[0].name);

    await user.click(screen.getByLabelText(students[2].name));
    await user.selectOptions(screen.getByLabelText("MBTI preset"), "INFP");
    await user.click(screen.getByRole("button", { name: "Persona 저장" }));

    await screen.findByRole("button", { name: "Simulation 시작" });
    await user.click(screen.getByRole("button", { name: "Simulation 시작" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Simulation이 이미 시작되어 있습니다."
    );

    // 재동기화 GET 요청이 실제로 나갔는지 확인
    const [syncUrl, syncOptions] = fetchMock.mock.calls[4];
    expect(syncUrl).toContain("/v1/simulations/sim_01/user-persona");
    expect(syncOptions?.method ?? "GET").toBe("GET");

    // 서버 상태(locked: true)로 동기화되어 입력이 잠긴다.
    await waitFor(() => {
      expect(screen.getByText(/Simulation이 시작되어/)).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: "Persona 저장" })
    ).not.toBeInTheDocument();
  });

  it("400 오류 시 서버 message를 그대로 표시한다", async () => {
    const fetchMock = mockInitialLoad();
    fetchMock.mockImplementationOnce(() =>
      response(
        {
          code: "INVALID_PERSONALITY_CONFIGURATION",
          message: "선택한 MBTI의 허용 범위를 벗어난 성격값이 있습니다.",
          details: { field: "extraversion", value: 20, allowed_min: -45, allowed_max: 5 },
        },
        400
      )
    );
    const user = userEvent.setup();

    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);
    await screen.findByLabelText(students[0].name);
    await user.click(screen.getByLabelText(students[0].name));
    await user.selectOptions(screen.getByLabelText("MBTI preset"), "ISTJ");
    await user.click(screen.getByRole("button", { name: "Persona 저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "선택한 MBTI의 허용 범위를 벗어난 성격값이 있습니다."
    );
  });

  it("409 오류 시 잠금 안내 메시지를 표시한다", async () => {
    const fetchMock = mockInitialLoad();
    fetchMock.mockImplementationOnce(() =>
      response(
        {
          code: "CONFLICT",
          message: "Simulation 시작 이후에는 User Persona 성격을 변경할 수 없습니다.",
          details: { agent_id: "student-01", persona_locked_at: "2026-08-05T07:30:00Z" },
        },
        409
      )
    );
    const user = userEvent.setup();

    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);
    await screen.findByLabelText(students[0].name);
    await user.click(screen.getByLabelText(students[0].name));
    await user.selectOptions(screen.getByLabelText("MBTI preset"), "ISTJ");
    await user.click(screen.getByRole("button", { name: "Persona 저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/변경할 수 없습니다/);
  });

  it("config 조회 자체가 실패하면 에러만 표시하고 폼을 렌더링하지 않는다", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({}, 500));

    render(<UserPersonaSetup simulationId="sim_01" students={students} token="t" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("서버 오류가 발생했습니다.");
    expect(screen.queryByLabelText("MBTI preset")).not.toBeInTheDocument();
  });
});
