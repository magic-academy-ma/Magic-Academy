import { useEffect, useState } from "react";
import "./App.css";

export default function App() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("http://localhost:8000/students/")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`학생 목록 조회에 실패했습니다. (${res.status})`);
        }
        return res.json();
      })
      .then((data) => {
        setStudents(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <p>불러오는 중...</p>;
  if (error) return <p>오류: {error}</p>;

  return (
    <div className="container">
      <h1>마법 대학교 학생 목록</h1>
      <p className="subtitle">학생 수: {students.length}명</p>
      <table>
        <thead>
          <tr>
            <th>이름</th>
            <th>학년</th>
            <th>전공</th>
            <th>기숙사</th>
            <th>주인공</th>
          </tr>
        </thead>
        <tbody>
          {students.map((s) => (
            <tr key={s.id} className={s.is_user_persona ? "persona" : ""}>
              <td>{s.name}</td>
              <td>{s.grade}학년</td>
              <td>{s.major}</td>
              <td>{s.dormitory}</td>
              <td>{s.is_user_persona ? "★" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
