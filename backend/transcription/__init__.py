def __getattr__(name):
    if name == "InterviewPipeline":
        from .main import InterviewPipeline
        return InterviewPipeline
    raise AttributeError(name)
